# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018, 2019, 2020, 2021, 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""REANA-Server utils."""

import base64
import csv
import io
import json
import logging
import os
import pathlib
import secrets
import sys
import shutil
from typing import Dict, List, Optional, Union
from uuid import UUID, uuid4

import click
import requests
import yaml
from flask import url_for
from jinja2 import Environment, PackageLoader, select_autoescape
from marshmallow.exceptions import ValidationError
from marshmallow.validate import Email
from urllib import parse as urlparse

from reana_commons.config import REANAConfig, REANA_WORKFLOW_UMASK, SHARED_VOLUME_PATH
from reana_commons.email import send_email
from reana_commons.errors import REANAQuotaExceededError, REANAValidationError
from reana_commons.k8s.secrets import REANAUserSecretsStore
from reana_commons.utils import get_quota_resource_usage
from reana_commons.yadage import yadage_load_from_workspace
from reana_db.database import Session
from reana_db.models import (
    ResourceType,
    ResourceUnit,
    RunStatus,
    User,
    UserResource,
    UserTokenStatus,
    UserTokenType,
    Workflow,
)
from reana_db.utils import get_default_quota_resource
from sqlalchemy.exc import (
    IntegrityError,
    InvalidRequestError,
    SQLAlchemyError,
    StatementError,
)

from reana_server.api_client import current_workflow_submission_publisher
from reana_server.complexity import (
    get_workflow_min_job_memory,
    estimate_complexity,
    validate_job_memory_limits,
)
from reana_server.config import (
    ADMIN_EMAIL,
    ADMIN_USER_ID,
    REANA_GITLAB_URL,
    REANA_HOSTNAME,
    REANA_USER_EMAIL_CONFIRMATION,
    REANA_WORKFLOW_SCHEDULING_POLICY,
    REANA_WORKFLOW_SCHEDULING_POLICIES,
    REANA_QUOTAS_DOCS_URL,
    WORKSPACE_RETENTION_PERIOD,
    DEFAULT_WORKSPACE_RETENTION_RULE,
)
from reana_server.validation import validate_retention_rule


def is_uuid_v4(uuid_or_name):
    """Check if given string is a valid UUIDv4."""
    # Based on https://gist.github.com/ShawnMilo/7777304
    try:
        uuid = UUID(uuid_or_name, version=4)
    except Exception:
        return False

    return uuid.hex == uuid_or_name.replace("-", "")


def create_user_workspace(user_workspace_path):
    """Create user workspace directory."""
    if not os.path.isdir(user_workspace_path):
        os.umask(REANA_WORKFLOW_UMASK)
        os.makedirs(user_workspace_path, exist_ok=True)


def get_fetched_workflows_dir(user_id: str) -> str:
    """Return temporary directory for fetching workflow files."""
    tmpdir = os.path.join(
        SHARED_VOLUME_PATH, "users", user_id, "workflowsfetched", str(uuid4())
    )
    create_user_workspace(tmpdir)
    return tmpdir


def get_quota_excess_message(user) -> str:
    """Return detailed quota excess message.

    :param user: User whose quota needs to be checked.
    """
    quota = user.get_quota_usage()
    message = "User quota exceeded.\n"
    for resource_type, resource in quota.items():
        limit = resource.get("limit", {}).get("raw", 0)
        usage = resource.get("usage", {}).get("raw", 0)
        if 0 < limit <= usage:
            resource_usage, _ = get_quota_resource_usage(resource, "human_readable")
            message += f"Resource: {resource_type}, usage: {resource_usage}\n"

    message += f"Please see: {REANA_QUOTAS_DOCS_URL}"
    return message


def prevent_disk_quota_excess(user, bytes_to_sum: int, action=Optional[str]):
    """
    Prevent potential disk quota excess.

    E.g. when uploading big files or launching new workflows.

    :param user: User whose quota needs to be checked.
    :param bytes_to_sum: Bytes to be added to the user's quota.
    :param action: Optional action description used for custom error messages.
    """
    disk_resource = get_default_quota_resource(ResourceType.disk.name)
    user_resource = UserResource.query.filter_by(
        user_id=user.id_, resource_id=disk_resource.id_
    ).first()
    if (
        user_resource.quota_limit > 0
        and user_resource.quota_used + bytes_to_sum > user_resource.quota_limit
    ):
        human_readable_limit = ResourceUnit.human_readable_unit(
            ResourceUnit.bytes_, user_resource.quota_limit
        )
        if not action:
            action = "This action"
        raise REANAQuotaExceededError(
            f"{action} would exceed the disk quota limit "
            f"({human_readable_limit}). Aborting. Please see: {REANA_QUOTAS_DOCS_URL}"
        )


def remove_fetched_workflows_dir(tmpdir: str) -> None:
    """Remove temporary directory used for fetching workflow files."""
    if tmpdir and os.path.isdir(tmpdir):
        shutil.rmtree(tmpdir)


def mv_workflow_files(source: str, target: str) -> None:
    """Move files from one directory to another."""
    for entry in os.listdir(source):
        shutil.move(os.path.join(source, entry), target)


# FIXME: use `is_relative_to` from the standard library when moving to Python 3.9
def is_relative_to(path: pathlib.Path, base: pathlib.Path) -> bool:
    """Check whether `path` is contained inside `base`."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def filter_input_files(workspace: Union[str, pathlib.Path], reana_spec: Dict) -> None:
    """Delete the files and directories not specified as inputs in the specification.

    :param workspace: Path to the directory containing the files to be filtered.
    :param reana_spec: REANA specification used to decide which files to keep.
    """
    inputs = reana_spec.get("inputs", {})
    files = inputs.get("files", [])
    directories = inputs.get("directories", [])

    if isinstance(workspace, str):
        workspace = pathlib.Path(workspace)

    for file in files:
        file_path = workspace / file
        if not file_path.exists():
            raise REANAValidationError(f"Input file not found: {file}")

    for directory in directories:
        directory_path = workspace / directory
        if not directory_path.exists():
            raise REANAValidationError(f"Input directory not found: {directory}")

    paths = [pathlib.Path(path) for path in files + directories]
    filtered = workspace / f"filtered-{uuid4()}"
    filtered.mkdir()

    # Move input files to the temporary `filtered` directory
    for path in paths:
        full_source_path = workspace / path
        full_target_path = filtered / path
        # Create target directory if it does not exist
        full_target_path.parent.mkdir(parents=True, exist_ok=True)
        full_source_path.replace(full_target_path)

    # Delete remaining files in the workspace
    for path in workspace.iterdir():
        if path == filtered:
            continue
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            shutil.rmtree(path)

    # Move the contents of the temporary `filtered` directory to the workspace
    for path in filtered.iterdir():
        path.replace(workspace / path.name)

    # Remove temporary `filtered` directory
    filtered.rmdir()


def get_user_from_token(access_token):
    """Validate that the token provided is valid."""
    user = (
        Session.query(User)
        .join(User.tokens)
        .filter_by(token=access_token, type_=UserTokenType.reana)
    ).one_or_none()
    if not user:
        raise ValueError("Token not valid.")
    if user.access_token_status == UserTokenStatus.revoked.name:
        raise ValueError("User access token revoked.")
    return user


def publish_workflow_submission(workflow, user_id, parameters):
    """Publish workflow submission."""
    from reana_server.status import NodesStatus

    Workflow.update_workflow_status(Session, workflow.id_, RunStatus.queued)

    scheduling_policy = REANA_WORKFLOW_SCHEDULING_POLICY
    if scheduling_policy not in REANA_WORKFLOW_SCHEDULING_POLICIES:
        raise ValueError(
            'Workflow scheduling policy "{0}" is not valid.'.format(scheduling_policy)
        )

    # No need to estimate the complexity for "fifo" strategy
    if scheduling_policy == "fifo":
        workflow_priority = 0
        workflow_min_job_memory = 0
    else:
        total_cluster_memory = NodesStatus().get_total_memory()
        complexity = _calculate_complexity(workflow)
        workflow_priority = workflow.get_priority(total_cluster_memory)
        workflow_min_job_memory = get_workflow_min_job_memory(complexity)
        validate_job_memory_limits(complexity)
    current_workflow_submission_publisher.publish_workflow_submission(
        user_id=str(user_id),
        workflow_id_or_name=str(workflow.id_),
        parameters=parameters,
        priority=workflow_priority,
        min_job_memory=workflow_min_job_memory,
    )


def _calculate_complexity(workflow):
    """Place workflow in queue and calculate and set its complexity."""
    complexity = estimate_complexity(workflow.type_, workflow.reana_specification)
    workflow.complexity = complexity
    Session.commit()
    return complexity


def _load_and_save_yadage_spec(workflow: Workflow, operational_options: Dict):
    """Load and save in DB the Yadage workflow specification."""
    operational_options.update({"accept_metadir": True})
    toplevel = operational_options.get("toplevel", "")
    workflow.reana_specification = yadage_load_from_workspace(
        workflow.workspace_path,
        workflow.reana_specification,
        toplevel,
    )
    Session.commit()


def _get_users(_id, email, user_access_token, admin_access_token):
    """Return all users matching search criteria."""
    admin = Session.query(User).filter_by(id_=ADMIN_USER_ID).one_or_none()
    if admin_access_token != admin.access_token:
        raise ValueError("Admin access token invalid.")
    search_criteria = dict()
    if _id:
        search_criteria["id_"] = _id
    if email:
        search_criteria["email"] = email
    query = Session.query(User).filter_by(**search_criteria)
    if user_access_token:
        query = query.join(User.tokens).filter_by(
            token=user_access_token, type_=UserTokenType.reana
        )
    return query.all()


def _create_user(email, user_access_token, admin_access_token):
    """Create user with provided credentials."""
    try:
        admin = Session.query(User).filter_by(id_=ADMIN_USER_ID).one_or_none()
        if admin_access_token != admin.access_token:
            raise ValueError("Admin access token invalid.")
        if not user_access_token:
            user_access_token = secrets.token_urlsafe(16)
        user_parameters = dict(access_token=user_access_token)
        user_parameters["email"] = email
        user = User(**user_parameters)
        Session.add(user)
        Session.commit()
    except (InvalidRequestError, IntegrityError):
        Session.rollback()
        raise ValueError("Could not create user, " "possible constraint violation")
    return user


def _export_users(admin_access_token):
    """Export all users in database as csv.

    :param admin_access_token: Admin access token.
    :type admin_access_token: str
    """
    admin = User.query.filter_by(id_=ADMIN_USER_ID).one_or_none()
    if admin_access_token != admin.access_token:
        raise ValueError("Admin access token invalid.")
    csv_file_obj = io.StringIO()
    csv_writer = csv.writer(csv_file_obj, dialect="unix")
    for user in User.query.all():
        csv_writer.writerow(
            [user.id_, user.email, user.access_token, user.username, user.full_name]
        )
    return csv_file_obj


def _import_users(admin_access_token, users_csv_file):
    """Import list of users to database.

    :param admin_access_token: Admin access token.
    :type admin_access_token: str
    :param users_csv_file: CSV file object containing a list of users.
    :type users_csv_file: _io.TextIOWrapper
    """
    admin = User.query.filter_by(id_=ADMIN_USER_ID).one_or_none()
    if admin_access_token != admin.access_token:
        raise ValueError("Admin access token invalid.")
    csv_reader = csv.reader(users_csv_file)
    for row in csv_reader:
        user = User(
            id_=row[0],
            email=row[1],
            access_token=row[2],
            username=row[3],
            full_name=row[4],
        )
        Session.add(user)
    Session.commit()


def _create_and_associate_oauth_user(sender, account_info, **kwargs):
    user_email = account_info["user"]["email"]
    user_fullname = account_info["user"]["profile"]["full_name"]
    username = account_info["user"]["profile"]["username"]
    return _create_and_associate_reana_user(user_email, user_fullname, username)


def _send_confirmation_email(confirm_token, user):
    """Compose and send sign-up confirmation email."""
    email_body = JinjaEnv.render_template(
        "emails/email_confirmation.txt",
        user_full_name=user.full_name,
        reana_hostname=REANA_HOSTNAME,
        ui_config=REANAConfig.load("ui"),
        sender_email=ADMIN_EMAIL,
        confirm_token=confirm_token,
    )
    send_email(user.email, "Confirm your REANA email address", email_body)


def _create_and_associate_local_user(sender, user, **kwargs):
    # TODO: Add fullname and username in sign up form eventually?
    user_email = user.email
    user_fullname = user.email
    username = user.email
    reana_user = _create_and_associate_reana_user(user_email, user_fullname, username)
    if REANA_USER_EMAIL_CONFIRMATION:
        _send_confirmation_email(kwargs.get("confirm_token"), reana_user)
    return reana_user


def _create_and_associate_reana_user(email, fullname, username):
    try:
        search_criteria = dict()
        search_criteria["email"] = email
        users = Session.query(User).filter_by(**search_criteria).all()
        if users:
            user = users[0]
        else:
            user_parameters = dict(email=email, full_name=fullname, username=username)
            user = User(**user_parameters)
            Session.add(user)
            Session.commit()
    except (InvalidRequestError, IntegrityError):
        Session.rollback()
        raise ValueError("Could not create user, possible constraint violation")
    except Exception:
        raise ValueError("Could not create user")
    return user


def _get_user_from_invenio_user(id):
    user = Session.query(User).filter_by(email=id).one_or_none()
    if not user:
        raise ValueError("No users registered with this id")
    if user.access_token_status == UserTokenStatus.revoked.name:
        raise ValueError("User access token revoked.")
    return user


def _get_reana_yaml_from_gitlab(webhook_data, user_id):
    gitlab_api = (
        REANA_GITLAB_URL
        + "/api/v4/projects/{0}"
        + "/repository/files/{1}/raw?ref={2}&access_token={3}"
    )
    reana_yaml = "reana.yaml"
    if webhook_data["object_kind"] == "push":
        branch = webhook_data["project"]["default_branch"]
        commit_sha = webhook_data["checkout_sha"]
    elif webhook_data["object_kind"] == "merge_request":
        branch = webhook_data["object_attributes"]["source_branch"]
        commit_sha = webhook_data["object_attributes"]["last_commit"]["id"]
    secrets_store = REANAUserSecretsStore(str(user_id))
    gitlab_token = secrets_store.get_secret_value("gitlab_access_token")
    project_id = webhook_data["project"]["id"]
    yaml_file = requests.get(
        gitlab_api.format(project_id, reana_yaml, branch, gitlab_token)
    )
    return (
        yaml.load(yaml_file.content, Loader=yaml.FullLoader),
        webhook_data["project"]["path_with_namespace"],
        webhook_data["project"]["name"],
        branch,
        commit_sha,
    )


def _fail_gitlab_commit_build_status(
    user: User, git_repo: str, git_ref: str, description: str
):
    """Send request to Gitlab to fail commit build status.

    HTTP errors will be ignored.
    """
    state = "failed"
    system_name = "reana"
    git_repo = urlparse.quote_plus(git_repo)
    description = urlparse.quote_plus(description)

    secret_store = REANAUserSecretsStore(user.id_)
    gitlab_access_token = secret_store.get_secret_value("gitlab_access_token")
    commit_status_url = (
        f"{REANA_GITLAB_URL}/api/v4/projects/{git_repo}/statuses/"
        f"{git_ref}?access_token={gitlab_access_token}&state={state}"
        f"&description={description}&name={system_name}"
    )
    requests.post(commit_status_url)


def _format_gitlab_secrets(gitlab_response):
    access_token = json.loads(gitlab_response)["access_token"]
    user = json.loads(
        requests.get(
            REANA_GITLAB_URL + "/api/v4/user?access_token={0}".format(access_token)
        ).content
    )
    return {
        "gitlab_access_token": {
            "value": base64.b64encode(access_token.encode("utf-8")).decode("utf-8"),
            "type": "env",
        },
        "gitlab_user": {
            "value": base64.b64encode(user["username"].encode("utf-8")).decode("utf-8"),
            "type": "env",
        },
    }


def _get_gitlab_hook_id(project_id, gitlab_token):
    """Return REANA hook id from a GitLab project if it is connected.

    By checking its webhooks and comparing them to REANA ones.

    :param response: Flask response.
    :param project_id: Project id on GitLab.
    :param gitlab_token: GitLab token.
    """
    reana_hook_id = None
    gitlab_hooks_url = (
        REANA_GITLAB_URL
        + "/api/v4/projects/{0}/hooks?access_token={1}".format(project_id, gitlab_token)
    )
    response_json = requests.get(gitlab_hooks_url).json()
    create_workflow_url = url_for("workflows.create_workflow", _external=True)
    if response_json:
        reana_hook_id = next(
            (
                hook["id"]
                for hook in response_json
                if hook["url"] and hook["url"] == create_workflow_url
            ),
            None,
        )
    return reana_hook_id


class RequestStreamWithLen(object):
    """Wrap ``request.stream`` object to have ``__len__`` attribute.

    Users can upload files to REANA through REANA-Server (RS). RS passes then
    the content of the file uploads to the next REANA component,
    REANA-Workflow-Controller (RWC).

    In order for this operation to be efficient we read the user stream upload
    using ``werkzeug`` streams through ``request.stream``. Then, to pass this
    stream to RWC without creating memory leaks we stream upload the
    ``request.stream`` content using the Requests library. However, the
    Request library is not aware of how the size of the stream is represented
    in ``werkzeug`` (``limit`` attribute), Requests only understands
    ``len(stream)`` or ``stream.len``, see more here
    https://github.com/psf/requests/blob/3e7d0a873f838e0001f7ac69b1987147128a7b5f/requests/utils.py#L108-L166

    This class provides the necessary attributes for compatibility with
    Requests stream upload.
    """

    def __init__(self, limitedstream):
        """Wrap the stream to have ``len``."""
        self.limitedstream = limitedstream

    def read(self, *args, **kwargs):
        """Expose ``request.stream``s read method."""
        return self.limitedstream.read(*args, **kwargs)

    def __len__(self):
        """Expose the length of the ``request.stream``."""
        if not hasattr(self.limitedstream, "limit"):
            return 0
        return self.limitedstream.limit


def get_workspace_retention_rules(
    retention_days: Optional[Dict[str, int]]
) -> List[Dict[str, any]]:
    """Validate and return a list of retention rules.

    :raises reana_commons.errors.REANAValidationError: in case one of the rules is not valid
    """
    retention_rules = []
    if retention_days:
        for rule, days in retention_days.items():
            validate_retention_rule(rule, days)
            retention_rules.append({"workspace_files": rule, "retention_days": days})

    # Insert a default rule in case it's not present
    if not any(
        rule["workspace_files"] == DEFAULT_WORKSPACE_RETENTION_RULE
        for rule in retention_rules
    ):
        retention_rules.append(
            {
                "workspace_files": DEFAULT_WORKSPACE_RETENTION_RULE,
                "retention_days": WORKSPACE_RETENTION_PERIOD,
            }
        )
    return retention_rules


def clone_workflow(workflow, reana_spec, restart_type):
    """Create a copy of workflow in DB for restarting."""
    reana_specification = reana_spec or workflow.reana_specification
    retention_days = reana_specification.get("workspace", {}).get("retention_days")
    retention_rules = get_workspace_retention_rules(retention_days)
    try:
        cloned_workflow = Workflow(
            id_=str(uuid4()),
            name=workflow.name,
            owner_id=workflow.owner_id,
            reana_specification=reana_spec or workflow.reana_specification,
            type_=restart_type or workflow.type_,
            logs="",
            workspace_path=workflow.workspace_path,
            restart=True,
            run_number=workflow.run_number,
        )
        Session.add(cloned_workflow)
        Session.object_session(cloned_workflow).commit()
        workflow.inactivate_workspace_retention_rules()
        cloned_workflow.set_workspace_retention_rules(retention_rules)
        return cloned_workflow
    except SQLAlchemyError as e:
        message = "Database connection failed, please retry."
        logging.error(
            f"Error while creating {cloned_workflow.id_}: {message}\n{e}", exc_info=True
        )


def _get_user_by_criteria(id_, email):
    """Get user filtering first by id, then by email."""
    criteria = dict()
    try:
        if id_:
            criteria["id_"] = id_
        elif email:
            criteria["email"] = email
        return User.query.filter_by(**criteria).one_or_none()
    except StatementError as e:
        print(e)
        return None


def _validate_password(ctx, param, value):
    if len(value) < 6:
        click.secho("ERROR: Password length must be at least 6 characters", fg="red")
        sys.exit(1)
    return value


def is_valid_email(value: str) -> bool:  # noqa: D103
    try:
        validator = Email()
        validator(value)
        return True
    except ValidationError:
        return False


def _validate_email(ctx, param, value):
    """Validate email callback for click CLI option."""
    if not is_valid_email(value):
        click.secho("ERROR: Invalid email format", fg="red")
        sys.exit(1)
    return value


class JinjaEnv:
    """Jinja Environment singleton instance."""

    _instance = None

    @staticmethod
    def _get():
        if JinjaEnv._instance is None:
            JinjaEnv._instance = Environment(
                loader=PackageLoader("reana_server", "templates"),
                autoescape=select_autoescape(["html", "xml"]),
            )
        return JinjaEnv._instance

    @staticmethod
    def render_template(template_path, **kwargs):
        """Render template replacing kwargs appropriately."""
        template = JinjaEnv._get().get_template(template_path)
        return template.render(**kwargs)

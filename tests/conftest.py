# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018, 2019, 2020, 2021, 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Pytest configuration for REANA-Workflow-Controller."""

from __future__ import absolute_import, print_function

from datetime import datetime, timedelta
import os


import flask_login
import pytest
from mock import Mock, patch

from reana_db.models import (
    WorkspaceRetentionAuditLog,
    WorkspaceRetentionRule,
    WorkspaceRetentionRuleStatus,
)

from reana_server.factory import create_app


@pytest.fixture(scope="module")
def base_app(tmp_shared_volume_path):
    """Flask application fixture."""
    config_mapping = {
        "AVAILABLE_WORKFLOW_ENGINES": "serial",
        "SERVER_NAME": "localhost:5000",
        "SECRET_KEY": "SECRET_KEY",
        "TESTING": True,
        "FLASK_ENV": "development",
        "SHARED_VOLUME_PATH": tmp_shared_volume_path,
        "SQLALCHEMY_DATABASE_URI": os.getenv("REANA_SQLALCHEMY_DATABASE_URI"),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "APP_THEME": None,
        "THEME_ICONS": None,
    }
    app_ = create_app(config_mapping=config_mapping)
    return app_


@pytest.fixture()
def _get_user_mock():
    mocked_user = Mock(is_authenticated=False, roles=[])
    mocked_get_user = Mock(return_value=mocked_user)
    with patch("flask_login.utils._get_user", mocked_get_user):
        yield flask_login.utils._get_user


@pytest.fixture()
def workflow_with_retention_rules(sample_serial_workflow_in_db, session):
    workflow = sample_serial_workflow_in_db
    workflow.reana_specification = dict(workflow.reana_specification)
    workflow.reana_specification["inputs"] = {
        "files": ["input.txt", "to_be_deleted/input.txt"],
        "directories": ["inputs"],
    }
    workflow.reana_specification["outputs"] = {
        "files": ["output.txt"],
        "directories": ["outputs", "to_be_deleted/outputs"],
    }
    current_time = datetime.now()
    workflow.retention_rules = [
        WorkspaceRetentionRule(
            workflow_id=workflow.id_,
            workspace_files="inputs",
            retention_days=1,
            status=WorkspaceRetentionRuleStatus.active,
            apply_on=current_time - timedelta(days=1),
        ),
        WorkspaceRetentionRule(
            workflow_id=workflow.id_,
            workspace_files="**/*.txt",
            retention_days=1,
            status=WorkspaceRetentionRuleStatus.active,
            apply_on=current_time - timedelta(days=1),
        ),
        WorkspaceRetentionRule(
            workflow_id=workflow.id_,
            workspace_files="to_be_deleted",
            retention_days=1,
            status=WorkspaceRetentionRuleStatus.active,
            apply_on=current_time - timedelta(days=1),
        ),
        WorkspaceRetentionRule(
            workflow_id=workflow.id_,
            workspace_files="**/*",
            retention_days=3,
            status=WorkspaceRetentionRuleStatus.active,
            apply_on=current_time + timedelta(days=1),
        ),
    ]
    session.add_all(workflow.retention_rules)
    session.add(workflow)
    session.commit()

    yield workflow

    session.query(WorkspaceRetentionAuditLog).delete()
    session.query(WorkspaceRetentionRule).delete()
    session.commit()

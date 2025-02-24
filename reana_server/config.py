# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2017, 2018, 2019, 2020, 2021, 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Flask application configuration."""

import copy
import json
import os
import re

from distutils.util import strtobool
from limits.util import parse
from invenio_app.config import APP_DEFAULT_SECURE_HEADERS
from invenio_oauthclient.contrib import cern_openid
from reana_commons.config import REANA_INFRASTRUCTURE_COMPONENTS_HOSTNAMES
from reana_commons.job_utils import kubernetes_memory_to_bytes

# This database URI import is necessary for Invenio-DB
from reana_db.config import SQLALCHEMY_DATABASE_URI

SQLALCHEMY_TRACK_MODIFICATIONS = False
"""Track modifications flag."""

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000000"

SHARED_VOLUME_PATH = os.getenv("SHARED_VOLUME_PATH", "/var/reana")

REANA_HOSTNAME = os.getenv("REANA_HOSTNAME")

REANA_SSO_CERN_CONSUMER_KEY = os.getenv("CERN_CONSUMER_KEY", "CHANGE_ME")

REANA_SSO_CERN_CONSUMER_SECRET = os.getenv("CERN_CONSUMER_SECRET", "CHANGE_ME")

REANA_KUBERNETES_JOBS_MEMORY_LIMIT = os.getenv("REANA_KUBERNETES_JOBS_MEMORY_LIMIT")
"""Maximum memory limit for user job containers for workflow complexity estimation."""

REANA_KUBERNETES_JOBS_MEMORY_LIMIT_IN_BYTES = (
    kubernetes_memory_to_bytes(REANA_KUBERNETES_JOBS_MEMORY_LIMIT)
    if REANA_KUBERNETES_JOBS_MEMORY_LIMIT
    else 0
)
"""Maximum memory limit for user job containers in bytes."""

REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT = os.getenv(
    "REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT"
)
"""Maximum memory limit that users can assign to their job containers."""

REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT_IN_BYTES = (
    kubernetes_memory_to_bytes(REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT)
    if REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT
    else 0
)
"""Maximum memory limit that users can assign to their job containers in bytes."""

REANA_WORKFLOW_SCHEDULING_POLICY = os.getenv("REANA_WORKFLOW_SCHEDULING_POLICY", "fifo")

REANA_WORKFLOW_SCHEDULING_POLICIES = ["fifo", "balanced"]
"""REANA workflow scheduling policies.
- ``fifo``: first-in first-out strategy starting workflows as they come.
- ``balanced``: a weighted strategy taking into account existing multi-user workloads and the DAG complexity of incoming workflows.
"""

REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL = int(
    os.getenv("REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL", 9)
)
"""REANA workflow scheduling readiness check needed to assess whether the cluster is ready to start new workflows."""

REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL_VALUE_MAP = {
    0: "no_checks",
    1: "concurrent",
    2: "memory",
    9: "all_checks",
}
"""REANA workflow scheduling readiness check level value map:
- 0 = no readiness check; schedule new workflow as soon as they arrive;
- 1 = check for maximum number of concurrently running workflows; schedule new workflows if not exceeded;
- 2 = check for available cluster memory size; schedule new workflow only if it fits;
- 9 = perform all checks; satisfy all previous criteria.
"""

REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_VALUE = (
    REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL_VALUE_MAP.get(
        REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL, "all_checks"
    )
)
"""REANA workflow scheduling readiness check value."""

SUPPORTED_COMPUTE_BACKENDS = json.loads(os.getenv("REANA_COMPUTE_BACKENDS", "[]")) or []
"""List of supported compute backends."""

REANA_QUOTAS_DOCS_URL = "https://docs.reana.io/advanced-usage/user-quotas"


# Invenio configuration
# =====================
def _(x):
    """Identity function used to trigger string extraction."""
    return x


# Email configuration
# ===================
#: Email address for support.
SUPPORT_EMAIL = "info@reanahub.io"
#: Disable email sending by default.
MAIL_SUPPRESS_SEND = True

# Accounts
# ========
#: Redis URL
ACCOUNTS_SESSION_REDIS_URL = "redis://{host}:6379/1".format(
    host=REANA_INFRASTRUCTURE_COMPONENTS_HOSTNAMES["cache"]
)
#: Email address used as sender of account registration emails.
SECURITY_EMAIL_SENDER = SUPPORT_EMAIL
#: Email subject for account registration emails.
SECURITY_EMAIL_SUBJECT_REGISTER = _("Welcome to REANA Server!")

#: Enable session/user id request tracing. This feature will add X-Session-ID
#: and X-User-ID headers to HTTP response. You MUST ensure that NGINX (or other
#: proxies) removes these headers again before sending the response to the
#: client. Set to False, in case of doubt.
ACCOUNTS_USERINFO_HEADERS = True
#: Disable password recovery by users.
SECURITY_RECOVERABLE = False
REANA_USER_EMAIL_CONFIRMATION = strtobool(
    os.getenv("REANA_USER_EMAIL_CONFIRMATION", "true")
)
#: Enable user to confirm their email address.
SECURITY_CONFIRMABLE = REANA_USER_EMAIL_CONFIRMATION
if REANA_USER_EMAIL_CONFIRMATION:
    #: Disable user login without confirming their email address.
    SECURITY_LOGIN_WITHOUT_CONFIRMATION = False
    #: Value to be used for the confirmation email link in the API application.
    ACCOUNTS_REST_CONFIRM_EMAIL_ENDPOINT = "/confirm-email"
#: URL endpoint for login.
SECURITY_LOGIN_URL = "/signin"
#: Disable password change by users.
SECURITY_CHANGEABLE = False
#: Modify sign in validaiton error to avoid leaking extra information.
failed_signin_msg = ("Signin failed. Invalid user or password.", "error")
SECURITY_MSG_USER_DOES_NOT_EXIST = failed_signin_msg
SECURITY_MSG_PASSWORD_NOT_SET = failed_signin_msg
SECURITY_MSG_INVALID_PASSWORD = failed_signin_msg
SECURITY_MSG_PASSWORD_INVALID_LENGTH = failed_signin_msg

# CORS
# ====
REST_ENABLE_CORS = True
# change this only while developing
CORS_SEND_WILDCARD = True
CORS_SUPPORTS_CREDENTIALS = False

# Flask configuration
# ===================
# See details on
# http://flask.pocoo.org/docs/0.12/config/#builtin-configuration-values

#: Secret key - each installation (dev, production, ...) needs a separate key.
#: It should be changed before deploying.
SECRET_KEY = "CHANGE_ME"
#: Sets cookie with the secure flag by default
SESSION_COOKIE_SECURE = True
#: Sets session to be samesite to avoid CSRF attacks
SESSION_COOKIE_SAMESITE = "Lax"
#: Since HAProxy and Nginx route all requests no matter the host header
#: provided, the allowed hosts variable is set to localhost. In production it
#: should be set to the correct host and it is strongly recommended to only
#: route correct hosts to the application.

#: In production use the following configuration plus adding  the hostname/ip
#: of the reverse proxy in front of REANA-Server.
if REANA_HOSTNAME:
    APP_ALLOWED_HOSTS = [REANA_HOSTNAME]

# Security configuration
# ======================
PROXYFIX_CONFIG = {"x_proto": 1}
APP_DEFAULT_SECURE_HEADERS["content_security_policy"] = {}
APP_HEALTH_BLUEPRINT_ENABLED = False

# Rate limiting configuration using invenio-app
# ===========================


def _get_rate_limit(env_variable: str, default: str) -> str:
    env_value = os.getenv(env_variable, "")
    try:
        parse(env_value)
        return env_value
    except ValueError:
        return default


# Note: users that are connecting via reana-client will be treated as guests by the Invenio framework
RATELIMIT_GUEST_USER = _get_rate_limit("REANA_RATELIMIT_GUEST_USER", "20 per second")
RATELIMIT_AUTHENTICATED_USER = _get_rate_limit(
    "REANA_RATELIMIT_AUTHENTICATED_USER", "20 per second"
)
REANA_RATELIMIT_SLOW = _get_rate_limit("REANA_RATELIMIT_SLOW", "1/5 second")

RATELIMIT_PER_ENDPOINT = {
    "launch.launch": REANA_RATELIMIT_SLOW,
}

# Flask-Breadcrumbs needs this variable set
# =========================================
BREADCRUMBS_ROOT = "breadcrumbs"

# OAuth configuration
# ===================
OAUTH_REDIRECT_URL = "/signin_callback"

OAUTH_REMOTE_REST_APP = copy.deepcopy(cern_openid.REMOTE_REST_APP)

OAUTH_REMOTE_REST_APP.update(
    {
        "authorized_redirect_url": OAUTH_REDIRECT_URL,
        "error_redirect_url": OAUTH_REDIRECT_URL,
    }
)

OAUTHCLIENT_REST_DEFAULT_ERROR_REDIRECT_URL = OAUTH_REDIRECT_URL

OAUTHCLIENT_REMOTE_APPS = dict(
    cern_openid=OAUTH_REMOTE_REST_APP,
)

OAUTHCLIENT_REST_REMOTE_APPS = dict(
    cern_openid=OAUTH_REMOTE_REST_APP,
)

CERN_APP_OPENID_CREDENTIALS = dict(
    consumer_key=REANA_SSO_CERN_CONSUMER_KEY,
    consumer_secret=REANA_SSO_CERN_CONSUMER_SECRET,
)

DEBUG = True

SECURITY_PASSWORD_SALT = "security-password-salt"

SECURITY_SEND_REGISTER_EMAIL = False

# Gitlab Application configuration
# ================================
REANA_GITLAB_OAUTH_APP_ID = os.getenv("REANA_GITLAB_OAUTH_APP_ID", "CHANGE_ME")
REANA_GITLAB_OAUTH_APP_SECRET = os.getenv("REANA_GITLAB_OAUTH_APP_SECRET", "CHANGE_ME")
REANA_GITLAB_URL = "https://{}".format(os.getenv("REANA_GITLAB_HOST", "CHANGE_ME"))


# Email configuration
# ===================
ADMIN_EMAIL = os.getenv("REANA_EMAIL_SENDER", "CHANGE_ME")


# Workflow scheduler
# ==================
REANA_SCHEDULER_REQUEUE_SLEEP = float(os.getenv("REANA_SCHEDULER_REQUEUE_SLEEP", "15"))
"""How many seconds to wait between consuming workflows."""

REANA_SCHEDULER_REQUEUE_COUNT = float(os.getenv("REANA_SCHEDULER_REQUEUE_COUNT", "200"))
"""How many times to requeue workflow, in case of error or busy cluster, before failing it."""

# Workflow fetcher
# ================
WORKFLOW_SPEC_FILENAMES = ["reana.yaml", "reana.yml"]
"""Filenames to use when discovering workflow specifications."""

WORKFLOW_SPEC_EXTENSIONS = [".yaml", ".yml"]
"""Valid file extensions of workflow specifications."""

REGEX_CHARS_TO_REPLACE = re.compile("[^a-zA-Z0-9_]+")
"""Regex matching groups of characters that need to be replaced in workflow names."""

FETCHER_MAXIMUM_FILE_SIZE = 1024**3  # 1 GB
"""Maximum file size allowed when fetching workflow specifications."""

FETCHER_ALLOWED_SCHEMES = ["https", "http"]
"""Schemes allowed when fetching workflow specifications."""

FETCHER_REQUEST_TIMEOUT = 60
"""Timeout used when fetching workflow specifications."""

FETCHER_ALLOWED_GITLAB_HOSTNAMES = ["gitlab.com", "gitlab.cern.ch"]
"""GitLab instances allowed when fetching workflow specifications."""

LAUNCHER_ALLOWED_SNAKEMAKE_URLS = [
    "https://github.com/reanahub/reana-demo-cms-h4l",
    "https://github.com/reanahub/reana-demo-helloworld",
    "https://github.com/reanahub/reana-demo-root6-roofit",
    "https://github.com/reanahub/reana-demo-worldpopulation",
]
"""Allowed URLs when launching a Snakemake workflow."""

# Workspace retention rules
# ==================

WORKSPACE_RETENTION_PERIOD = int(os.getenv("WORKSPACE_RETENTION_PERIOD", "365"))
"""Maximum allowed period for workspace retention rules."""

DEFAULT_WORKSPACE_RETENTION_RULE = "**/*"
"""Workspace retention rule which will be applied to all the workflows by default."""

Changes
=======

Version 0.9.0 (UNRELEASED)
--------------------------

- Adds workspace retention rules validation to ``get_workspace_retention_rules`` function.
- Adds ``queue-consume`` command that can be used by REANA administrators to remove specific messages from the queue.
- Adds configuration environment variable to set an API rate limit for slow endpoints (``REANA_RATELIMIT_SLOW``).
- Adds new ``/api/launch`` endpoint that allows running workflows from remote sources.
- Adds the possibility to fetch the workflow specification from a remote URL.
- Adds REANA specification validation utilities.
- Adds `retention-rules-apply` command that can be used to apply pending retention rules.
- Changes workflow create endpoint to populate workspace retention rules for the workflow.
- Changes workflow list endpoint to return workspace retention rules for the workflow.
- Changes API rate limiter error messages to be more verbose.
- Changes workflow scheduler to allow defining the checks needed to assess whether the cluster can start new workflows.
- Changes the Invenio dependencies to the latest versions.
- Changes OAuth configuration to enable the new CERN SSO.
- Fixes issue when irregular number formats are passed to ``REANA_SCHEDULER_REQUEUE_COUNT``.
- Fixes GitLab integration error reporting in case user exceeds CPU or Disk quota usage limits.

Version 0.8.4 (2022-02-23)
--------------------------

- Changes workflow scheduler to count number of workflow retries.

Version 0.8.3 (2022-02-10)
--------------------------

- Adds Kubernetes job memory limits validation before publishing workflow submission.

Version 0.8.2 (2022-02-07)
--------------------------

- Adds email validation to the ``user-create`` command used by the REANA administrators.
- Adds workflow name validation to the ``create_workflow`` endpoint.
- Changes ``/api/info`` endpoint to return a list of supported compute backends.
- Changes ``/api/status`` endpoint to calculate the cluster health status based on the availablity instead of the usage.

Version 0.8.1 (2021-11-29)
--------------------------

- Changes ``quota-set`` command used by the REANA administrators to use the resource type along with a resource name for specifying the resource.
- Changes email validation used in ``create-admin-user`` command by the REANA administrators to be more permissive.

Version 0.8.0 (2021-11-22)
---------------------------

- Adds users quota accounting.
- Adds support for Snakemake workflow engine.
- Adds ``include_progress`` and ``include_workspace_size`` query args to workflow list endpoint.
- Adds workflow prioritization in the queue by complexity.
- Adds ``priority`` and ``min_job_memory`` params to workflow submission publisher.
- Adds Yadage workflow specification loading to ``start_workflow`` endpoint.
- Adds a check in scheduler if at least one workflow job could be started in Kubernetes.
- Adds configuration environment variable to set workflow scheduling policy (``REANA_WORKFLOW_SCHEDULING_POLICY``).
- Adds configuration environment variable to set a timeout between consuming workflows (``REANA_SCHEDULER_REQUEUE_SLEEP``).
- Adds configuration environment variable to set an API rate limiter (``REANA_RATELIMIT_AUTHENTICATED_USER``, ``REANA_RATELIMIT_GUEST_USER``).
- Adds new ``info`` endpoint allowing to retrieve information about cluster capabilities such as available workspaces.
- Changes workflow execution consumer to receive only one message at a time.
- Changes to PostgreSQL 12.8

Version 0.7.6 (2021-07-05)
--------------------------

- Changes internal dependencies.

Version 0.7.5 (2021-04-28)
--------------------------

- Adds support for listing files using glob patterns.
- Adds support for glob patterns and directory downloads, packaging the content into a zip file.

Version 0.7.4 (2021-03-17)
--------------------------

- Adds configuration to set a timeout between ``reana_ready`` checks. (``REANA_SCHEDULER_SECONDS_TO_WAIT_FOR_REANA_READY``)
- Fixes start workflow endpoint to work with unspecified ``operational_options`` parameter
- Fixes workflow scheduling bug in which failed worfklows would count as running, reaching ``REANA_MAX_CONCURRENT_BATCH_WORKFLOWS`` and therefore, blocking the ``job-submission`` queue.

Version 0.7.3 (2021-02-03)
--------------------------

- Adds optional email confirmation step after users sign up.
- Changes email notifications with enriched instructions on how to grant user tokens.

Version 0.7.2 (2020-11-24)
--------------------------

- Changes rate limiting defaults to allow up to 20 connections per second.
- Fixes minor code warnings.

Version 0.7.1 (2020-11-10)
--------------------------

- Fixes REANA <-> GitLab synchronisation for projects having additional external webhooks.
- Fixes restarting of Yadage and CWL workflows.
- Fixes conflicting ``kombu`` installation requirements by requiring Celery version 4.
- Changes ``/api/you`` endpoint to include REANA server version information.

Version 0.7.0 (2020-10-20)
--------------------------

- Adds new endpoint to request user tokens.
- Adds email notifications on relevant events such as user token granted/revoked.
- Adds new templating system for notification email bodies.
- Adds possibility to query logs for a single workflow step.
- Adds endpoint to retrieve the workflow specification used for the workflow run.
- Adds preview flag to download file endpoint.
- Adds validation of submitted operational options before starting a workflow.
- Adds possibility to upload empty files.
- Adds new block size option to specify the type of units to use for disk size.
- Adds a possibility to upload new workflow definitions before restarting a workflow.
- Adds new command to generate status report for the REANA administrators; useful as a cronjob.
- Adds user token management commands to grant and revoke user tokens.
- Adds support for local user management.
- Adds pinning of all Python dependencies allowing to easily rebuild component images at later times.
- Fixes bug related to rescheduling deleted workflows.
- Changes ``REANA_URL`` configuration variable to more precise ``REANA_HOSTNAME``.
- Changes workflow list endpoint response payload to include workflow progress information.
- Changes import/export commands with respect to new user model fields.
- Changes submodule installation in editable mode for live code updates for developers.
- Changes pre-requisites to Invenio-Accounts 1.3.0 to support REST API.
- Changes ``/api/me`` to ``/api/you`` endpoint due to conflict with Invenio-Accounts.
- Changes base image to use Python 3.8.
- Changes code formatting to respect ``black`` coding style.
- Changes documentation to single-page layout.

Version 0.6.1 (2020-05-25)
--------------------------

- Upgrades REANA-Commons package using latest Kubernetes Python client version.
- Pins Flask and Invenio dependencies to fix REANA 0.6 installation troubles.

Version 0.6.0 (2019-12-20)
--------------------------

- Fixes bug with big file uploads by using data streaming.
- Adds user login endpoints using OAuth, currently configured to work with CERN
  SSO but extensible to use other OAuth providers such as GitHub, more in `Invenio-OAuthClient <https://invenio-oauthclient.readthedocs.io/en/latest/>`_.
- Adds endpoints to integrate with GitLab (for retrieving user projects and creating/deleting webhooks).
- Adds new endpoint ``/me`` to retrieve user information.
- Improves security by allowing requests only with ``REANA_URL`` in the host header, avoiding host header injection attacks.
- Initialisation logs moved from ``stdout`` to ``/var/log/reana-server-init-output.log``.

Version 0.5.0 (2019-04-23)
--------------------------

- Adds new endpoint to compare two workflows. The output is a ``git`` like
  diff which can be configured to show differences at metadata level,
  workspace level or both.
- Adds new endpoint to retrieve workflow parameters.
- Adds new endpoint to query the disk usage of a given workspace.
- Adds new endpoints to delete and move files whithin the workspace.
- Adds new endpoints to open and close interactive sessions inside the
  workspace.
- Workflow start does not send start requests to REANA Workflow Controller
  straight away, instead it will decide whether REANA can execute it or queue
  it depending on a set of conditions, currently it depends on the number of
  running jobs in the cluster.
- Adds new administrator command to export and import all REANA users.

Version 0.4.0 (2018-11-06)
--------------------------

- Improves REST API documentation rendering.
- Enhances test suite and increases code coverage.
- Changes license to MIT.

Version 0.3.1 (2018-09-07)
--------------------------

- Harmonises date and time outputs amongst various REST API endpoints.
- Pins REANA-Commons, REANA-DB and Bravado dependencies.

Version 0.3.0 (2018-08-10)
--------------------------

- Adds support of Serial workflows.
- Adds API protection with API tokens.

Version 0.2.0 (2018-04-19)
--------------------------

- Adds support of Common Workflow Language workflows.
- Adds support of specifying workflow names in REST API requests.
- Improves error messages and information.

Version 0.1.0 (2018-01-30)
--------------------------

- Initial public release.

.. admonition:: Please beware

   Please note that REANA is in an early alpha stage of its development. The
   developer preview releases are meant for early adopters and testers. Please
   don't rely on released versions for any production purposes yet.

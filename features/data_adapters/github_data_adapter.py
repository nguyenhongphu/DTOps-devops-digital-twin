import json
import os
from datetime import datetime

from dateutil.relativedelta import relativedelta

from destinations import LOCAL_DATA_DIR, DATA_EXPORT_DIR
from utils.cache import Cache
from utils.cached_request import CachedRequest
from utils.config import Config
from utils.constants.twin_constants import TwinConstants
from utils.github_utils import GitHubUtils


class GitHubDataAdapter:
    def __init__(self, repo_url, branch='main', automation_run_history_timeframe_in_months=6):
        self.repo_url = repo_url
        self.branch = branch
        self.automation_run_history_timeframe_in_months = automation_run_history_timeframe_in_months
        self.owner, self.repo_name = GitHubUtils.get_owner_and_repo_name(repo_url)

    def _export_as_json(self, data, file_name):
        data_dir = os.path.join(DATA_EXPORT_DIR, self.owner, self.repo_name)

        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, file_name), 'w') as output_file:
            json.dump(data, output_file)

    @staticmethod
    def _get_commit_author(commit):
        # GitHub API 'quirk', sometimes only committer is set and author is None,
        # and sometimes author is set but committer is 'web-flow' when done via web UI, so we
        # give priority to the author field unless it is None.
        if commit['author'] is None:
            if commit['committer'] is None:
                author = "unknown"
            else:
                author = commit['committer']['login']
        else:
            author = commit['author']['login']

        # In some cases, it is still web-flow. Then, we use the ['commit]['author']['name'] field instead
        if author == 'web-flow' or author == 'unknown':
            return commit['commit']['author']['name']
        return author

    def _fetch_issues(self):
        api_url = f'https://api.github.com/repos/{self.owner}/{self.repo_name}/issues?state=all'
        return self._fetch_from_paginated_api(api_url)

    @staticmethod
    def _fetch_from_paginated_api(api_url):
        data = []
        headers = Config.get_github_request_header()
        if '?' in api_url:
            api_url += '&per_page=100'
        else:
            api_url += '?per_page=100'

        while api_url is not None:
            new_data, api_url = CachedRequest.get_paginated(api_url, headers=headers)
            data.extend(new_data)

        return data

    # Use with APIs that do not return arrays but instead an object with
    #     # {
    #     #   "total_count": 2,
    #     #   "data": [..]
    #     # }
    @staticmethod
    def _fetch_from_paginated_counted_api(api_url, data_object_key):
        data = []
        headers = Config.get_github_request_header()
        if '?' in api_url:
            api_url += '&per_page=100'
        else:
            api_url += '?per_page=100'

        while api_url is not None:
            new_data, api_url = CachedRequest.get_paginated(api_url, headers=headers)
            data.extend(new_data[data_object_key])

        return data

    def _fetch_workflows(self):
        api_url = f'https://api.github.com/repos/{self.owner}/{self.repo_name}/actions/workflows'

        return self._fetch_from_paginated_counted_api(api_url, 'workflows')

    def _fetch_releases(self):
        api_url = f'https://api.github.com/repos/{self.owner}/{self.repo_name}/releases'

        cached_data = Cache.load(api_url)
        if cached_data is not None:
            return cached_data

        all_releases = self._fetch_from_paginated_api(api_url)
        Cache.update(api_url, all_releases)
        return all_releases

    def _fetch_commits(self):
        api_url = f'https://api.github.com/repos/{self.owner}/{self.repo_name}/commits?sha={self.branch}'

        cached_data = Cache.load(api_url)
        if cached_data is not None:
            return cached_data

        all_commits = self._fetch_from_paginated_api(api_url)
        Cache.update(api_url, all_commits)
        return all_commits

    def _get_latest_commit_hash_in_release(self, tag_name):
        tag_object = CachedRequest.get_json(
            f'https://api.github.com/repos/{self.owner}/{self.repo_name}/git/refs/tags/{tag_name}',
            headers=Config().get_github_request_header())
        return tag_object['object']['sha']

    def fetch_twin_data(self, debug_options=None):
        self._export_commit_data_as_json(debug_options=debug_options)
        self._export_deployment_data_as_json(debug_options=debug_options)
        self._export_issue_data_as_json(debug_options=debug_options)
        self._export_automation_data_as_json(debug_options=debug_options)
        self._export_automation_runs_as_json(debug_options=debug_options)

    def _export_issue_data_as_json(self, debug_options=None):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        issues = self._fetch_issues()
        issue_data_list = []
        for issue in issues:
            issue_data = {
                'url': issue['url'],
                'id': issue['id'],
                'title': issue['title'],
                'state': issue['state'],
                'locked': issue['locked'],
                'user': issue['user'] if issue['user'] is not None else None,
                'assignee': issue['assignee'] if issue['assignee'] is not None else None,
                'milestone': issue['milestone'] if issue['milestone'] is not None else None,
                'comments': issue['comments'],
                'created_at': datetime.strptime(issue['created_at'], '%Y-%m-%dT%H:%M:%SZ').replace(
                    microsecond=0).isoformat(),
                'updated_at': issue['updated_at'],
                'closed_at': datetime.strptime(issue['closed_at'], '%Y-%m-%dT%H:%M:%SZ').replace(
                    microsecond=0).isoformat() if issue['closed_at'] is not None else None,
                'body': issue['body']
            }

            label_list = []
            for label in issue['labels']:
                label_id = label['id']
                label_data = {
                    'id': label_id,
                    'url': f'{self.repo_url}/labels/{label["name"]}',
                    'name': label['name'],
                    'color': label['color'],
                    'description': label['description'],
                }
                label_list.append(label_data)
            issue_data['labels'] = label_list

            issue_data_list.append(issue_data)
            if enable_logs:
                print(f'Added issue with id {issue["id"]}')

        self._export_as_json(issue_data_list, TwinConstants.ISSUES_DATA_FILE_NAME)

    def _export_deployment_data_as_json(self, debug_options=None):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        releases = self._fetch_releases()

        deployments_sorted = sorted(releases, key=lambda r: datetime.strptime(r['published_at'], '%Y-%m-%dT%H:%M:%SZ'))
        deployment_data = []
        for release in deployments_sorted:
            name = release['tag_name']

            latest_commit_hash = self._get_latest_commit_hash_in_release(name)
            url = self.repo_url + f'/releases/tag/{name}'
            commit_url = self.repo_url + f'/commit/{latest_commit_hash}'
            publish_date = release['published_at']
            deployment = {
                'id': release['id'],
                'name': name,
                'published_at': datetime.strptime(publish_date, '%Y-%m-%dT%H:%M:%SZ').replace(
                    microsecond=0).isoformat(),
                'url': url,
                'commit_url': commit_url,
                'latest_included_commit': latest_commit_hash,
                'previous_deployment': None if len(deployment_data) == 0 else deployment_data[-1]['name'],
            }
            if enable_logs:
                print(f'Deployment with tag {name} added.')
            deployment_data.append(deployment)

        self._export_as_json(deployment_data, TwinConstants.DEPLOYMENT_DATA_FILE_NAME)

    def _export_commit_data_as_json(self, debug_options=None):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        commits = self._fetch_commits()
        export_data = []
        for commit in reversed(commits):
            author = self._get_commit_author(commit)
            commit_data = {
                'message': commit['commit']['message'],
                'hash': commit['sha'],
                'author': author,
                'date': datetime.strptime(commit['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ').replace(
                    microsecond=0).isoformat(),
                'branch': self.branch,
                'url': (self.repo_url + f'/commit/{commit["sha"]}'),
                'parents': list(map(lambda c: c['sha'], commit['parents']))
            }
            export_data.append(commit_data)
            if enable_logs:
                print(f'Added commit with hash {commit["sha"]}.')

        self._export_as_json(export_data, TwinConstants.COMMIT_DATA_FILE_NAME)

    def _export_automation_data_as_json(self, debug_options=None):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        workflows = self._fetch_workflows()
        automation_data = []
        for wf_data in workflows:
            data = {
                'id': wf_data['id'],
                'name': wf_data['name'],
                'path': wf_data['path'],
                'created_at': datetime.strptime(wf_data['created_at'], '%Y-%m-%dT%H:%M:%S.%f%z').replace(
                    microsecond=0).isoformat(),
                'updated_at': datetime.strptime(wf_data['updated_at'], '%Y-%m-%dT%H:%M:%S.%f%z').replace(
                    microsecond=0).isoformat(),
                'url': wf_data['url'],
            }
            if enable_logs:
                print(f'Workflow {wf_data["name"]} data added.')
            automation_data.append(data)

        self._export_as_json(automation_data, TwinConstants.AUTOMATION_DATA_FILE_NAME)

    def _export_automation_runs_as_json(self, debug_options=None):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        workflows = self._fetch_workflows()
        automation_history = []
        for wf_data in workflows:
            earliest_valid_date = (datetime.now() - relativedelta(
                months=self.automation_run_history_timeframe_in_months)).isoformat()

            api_url = f'https://api.github.com/repos/{self.owner}/{self.repo_name}/actions/workflows/{wf_data["id"]}/runs' \
                      f'?per_page=100&created=>{earliest_valid_date}'

            workflow_runs = self._fetch_from_paginated_counted_api(api_url, 'workflow_runs')
            data = list(map(self._github_run_history_to_data_model, workflow_runs))

            if enable_logs:
                print(f"Fetched {len(workflow_runs)} runs for workflow {wf_data['name']}")
            automation_history.extend(data)

        self._export_as_json(automation_history, TwinConstants.AUTOMATION_HISTORY_FILE_NAME)

    @staticmethod
    def _github_run_history_to_data_model(data):
        return {
            'id': data['id'],
            'name': data['name'],
            'head_branch': data['head_branch'],
            'head_sha': data['head_sha'],
            'path': data['path'],
            'run_number': data['run_number'],
            'event': data['event'],
            'status': data['status'],
            'conclusion': data['conclusion'],
            'workflow_id': data['workflow_id'],
            'url': data['url'],
            'run_started_at': datetime.strptime(data['run_started_at'], '%Y-%m-%dT%H:%M:%SZ').replace(
                microsecond=0).isoformat(),
            'updated_at': datetime.strptime(data['updated_at'], '%Y-%m-%dT%H:%M:%SZ').replace(
                microsecond=0).isoformat(),
            'started_by': data.get('triggering_actor', {}).get('login', None),
            'run_attempt': data['run_attempt'],
        }

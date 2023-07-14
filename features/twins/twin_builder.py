import os

from features.twins.automations_twin import AutomationsTwin
from features.twins.deployments_twin import DeploymentsTwin
from features.twins.git_twin import GitTwin
from features.twins.project_management_twin import ProjectManagementTwin
from features.twins.twin_link_creator import TwinLinkCreator
from features.data_adapters.github.utils.github_utils import GitHubUtils
from utils.neo4j import Neo4j
from utils.constants.twin_constants import TwinConstants, DataTypes


class TwinBuilder:

    @staticmethod
    def construct_from_github_data_repo(repo_url, twin_name, debug_options=None, wipe_db=False):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        if wipe_db:
            Neo4j.wipe_database()
            if enable_logs:
                print(f'Wiped DB')

        raw_file_link = os.path.join(GitHubUtils.get_raw_file_link(repo_url), TwinConstants.DATA_EXPORT_DIR)

        commit_data = os.path.join(raw_file_link, DataTypes.COMMIT_DATA + '.json')
        deployment_data = os.path.join(raw_file_link, DataTypes.DEPLOYMENT_DATA + '.json')
        issue_data = os.path.join(raw_file_link, DataTypes.ISSUES_DATA + '.json')
        automation_data = os.path.join(raw_file_link, DataTypes.AUTOMATION_DATA + '.json')
        automation_history_data = os.path.join(raw_file_link, DataTypes.AUTOMATION_HISTORY + '.json')

        if enable_logs:
            print(f'Building twin from data source in {repo_url} using the following '
                  f'files:\n{commit_data}\n{deployment_data}\n{issue_data}\n{automation_data}')

        GitTwin.construct_from_json(commit_data)
        DeploymentsTwin.construct_from_json(deployment_data)
        ProjectManagementTwin.construct_from_json(issue_data)
        AutomationsTwin.construct_from_json(automation_data, automation_history_data)

        TwinLinkCreator.create_links(twin_name)

        TwinBuilder.print_usage_info()

    @staticmethod
    def print_usage_info():
        print(""""
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@    DONE CONSTRUCTING TWIN    @@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
        
Time to explore! Visit the graph at https://www.yworks.com/neo4j-explorer/
You might be interested in some queries:

@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@ View everything (not recommended for > 1000 nodes): @
@                                                     @
@                 match (n) return n                  @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@ View releases:                                      @
@                                                     @
@            match (n:Deployment) return n            @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@ View relationships between releases and commits:    @
@                                                     @
@ MATCH (n)-[:LATEST_INCLUDED_COMMIT]->(l)            @
@ RETURN n, l                                         @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
""")

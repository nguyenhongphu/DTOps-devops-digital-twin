import statistics
from datetime import timedelta, datetime
from typing import Callable

from features.twins.deployments_twin import DeploymentsTwin
from features.twins.git_twin import GitTwin
from utils.neo4j import Neo4j


# The cockpit of a digital twin is a layer above the data itself, it usually includes a user interface, for now
# it is just code that works on twin data.
class Cockpit:

    @staticmethod
    def get_all_releases(from_date=None, to_date=None):
        date_filter = ''
        if from_date is not None or to_date is not None:
            date_filter += 'WHERE '
            if from_date is not None:
                date_filter += f'datetime(deployment.published_at) >= datetime("{from_date.isoformat()}")'
            if to_date is not None:
                if from_date is not None:
                    date_filter += ' AND '
                date_filter += f'datetime(deployment.published_at) <= datetime("{to_date.isoformat()}")'

        query = f"""
            MATCH (deployment:Deployment)
            {date_filter}
            RETURN deployment.tag_name as tag_name, deployment.published_at as published_at
            """
        releases = Neo4j.get_graph().run(query).data()
        return sorted(releases, key=lambda r: datetime.fromisoformat(r['published_at']))

    @staticmethod
    def calculate_dora_deployment_frequency(from_date=None, to_date=None):
        deployment_dates = Cockpit.get_all_releases(from_date=from_date, to_date=to_date)

        if len(deployment_dates) <= 1:
            raise Exception('Not enough data to calculate deployment frequency.')

        parsed_dates = list(map(lambda x: datetime.fromisoformat(x['published_at']), deployment_dates))
        time_between_releases = [parsed_dates[i] - parsed_dates[i - 1] for i in range(1, len(parsed_dates))]

        return sum(time_between_releases, timedelta()) / (len(time_between_releases))

    @staticmethod
    def calculate_lead_time_from_commit_to_deployment(commit_hash, deployment_tag):
        return Neo4j.get_graph().run(f"""
        MATCH (deployment:Deployment {{tag_name: '{deployment_tag}'}}), 
        (commit:Commit {{hash: '{commit_hash}'}})
        RETURN duration.between(datetime(deployment.published_at), datetime(commit.date))
        """).evaluate()

    @staticmethod
    def calculate_dora_lead_time(deployment_tag=None, excluded_tags=None):
        filter_deployment = ''
        if deployment_tag is not None:
            filter_deployment = f" {{tag_name: '{deployment_tag}'}}"

        filter_tags = ''
        if excluded_tags is not None:
            excluded_tag_string = ','.join(list(map(lambda s: f"'{s}'", excluded_tags)))
            filter_tags = f" WHERE NOT deployment.tag_name IN [{excluded_tag_string}]"

        query = f"""
        MATCH (deployment:Deployment {filter_deployment})-[:INITIAL_DEPLOY]->(deployed_commit:Commit)
        {filter_tags}
        WITH duration.inSeconds(datetime(deployed_commit.date), datetime(deployment.published_at)) as lead_time
        RETURN lead_time
        """
        duration_list = Neo4j.get_graph().run(query).data()

        seconds_array = list(map(lambda d: d['lead_time'].seconds, duration_list))
        lead_time_in_s = statistics.mean(seconds_array) if len(seconds_array) > 0 else 0
        return timedelta(seconds=lead_time_in_s)

    @staticmethod
    def construct_digital_twin(repo_url, release_branch_name, debug_options=None, wipe_db=True):
        if wipe_db:
            Neo4j.wipe_database()

        GitTwin.construct_from_github_url(repo_url, branch_name=release_branch_name, debug_options=debug_options)
        DeploymentsTwin.construct(repo_url, debug_options=debug_options)
        Cockpit.print_usage_info()

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

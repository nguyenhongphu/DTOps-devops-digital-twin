import os

from git import Repo
from py2neo import Node, Relationship

from destinations import LOCAL_DATA_DIR
from utils.constants.graph_nodes import GraphNodes
from utils.constants.graph_relationships import GraphRelationships
from utils.neo4j import Neo4j


class GitTwin:

    @staticmethod
    def construct_from_json(json_url, debug_options=None):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']

        repo_owner_slash_name = json_url.split("https://github.com/")[1]
        repo_dir = f'{LOCAL_DATA_DIR}/{repo_owner_slash_name}'

        if not os.path.exists(repo_dir):
            if enable_logs:
                print('repo did not exist locally yet, cloning now')
            Repo.clone_from(json_url, repo_dir)
        elif enable_logs:
            print('found repo locally')

        GitTwin.construct_from_repo_path(path=repo_dir, branch_name=branch_name, repo_url=json_url,
                                         debug_options=debug_options)

    @staticmethod
    def construct_from_repo_path(path, branch_name, repo_url=None, debug_options=None, enable_branch_node=False):
        if debug_options is None:
            debug_options = {}
        enable_logs = 'enable_logs' in debug_options and debug_options['enable_logs']
        max_nodes = debug_options['max_nodes'] if 'max_nodes' in debug_options else None

        repo = Repo(path)
        repo.git.checkout(branch_name)
        repo.remotes.origin.pull()

        graph = Neo4j.get_graph()

        if enable_branch_node:
            branch_node = Node(GraphNodes.BRANCH, name=f'{branch_name}', url=f'{repo_url}/tree/{branch_name}')
            graph.create(branch_node)

        commits_added = 0
        for commit in repo.iter_commits(branch_name, reverse=True):
            # Allow limiting imported nodes for quicker debugging
            commits_added += 1
            if max_nodes is not None and commits_added > max_nodes:
                break

            # Do not add again if already exists - wipe db before importing to avoid this.
            match_current_commit = graph.nodes.match(GraphNodes.COMMIT, hash=commit.hexsha).first()
            if match_current_commit is not None:
                if enable_logs:
                    print(f'Commit with hash {commit.hexsha} already found, skipping')
                continue

            # Add commit node with attributes and branch relationship
            commit_url = None if repo_url is None else repo_url + f'/commit/{commit.hexsha}'

            commit_node = Node(GraphNodes.COMMIT, message=commit.message, hash=commit.hexsha,
                               date=commit.committed_datetime.replace(microsecond=0).isoformat(),
                               branch=branch_name,
                               url=commit_url)
            graph.create(commit_node)
            if enable_branch_node:
                branch_relation = Relationship(commit_node, GraphRelationships.ON_BRANCH, branch_node)
                graph.create(branch_relation)
            if enable_logs:
                print(f'Added commit with hash {commit.hexsha}')

            # Add relationship to parent node(s)
            for parent in commit.parents:
                parent_node = graph.nodes.match(GraphNodes.COMMIT, hash=parent.hexsha).first()
                if parent_node is not None:
                    print(f'Adding relationship to parent node {parent.hexsha}')
                    relation = Relationship(commit_node, GraphRelationships.PARENT, parent_node)
                    graph.create(relation)
                elif enable_logs:
                    print(f'Commit had parent node {parent.hexsha} but this node was not found in the graph')

        repo.close()

from utils.neo4j import Neo4j


class GitTwin:

    @staticmethod
    def construct_from_json(json_url):
        print(f'Constructing GitTwin from {json_url}')
        query = f'''
CALL apoc.periodic.iterate(
"
    CALL apoc.load.json('{json_url}') YIELD value RETURN value
",
"
    MERGE (c:Commit {{hash: value.hash}})
    SET
    c.message = value.message,
    c.date = value.date,
    c.branch = value.branch,
    c.url = value.url
    
    FOREACH (parentHash IN value.parents |
      MERGE (p:Commit {{hash: parentHash}})
      MERGE (c)-[:PARENT]->(p)
    )
    RETURN 1
",
{{batchSize: 1000, parallel: false}})
YIELD batch
'''
        result = Neo4j.run_query(query)
        print(result)

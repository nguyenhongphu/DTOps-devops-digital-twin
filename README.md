# DevOps Digital Twin

[![Python integration test](https://github.com/jangruenwaldt/devops-digital-twin/actions/workflows/ci.yaml/badge.svg)](https://github.com/jangruenwaldt/devops-digital-twin/actions/workflows/ci.yaml)
[![Create/update DevOps digital twin](https://github.com/jangruenwaldt/devops-digital-twin/actions/workflows/create_twin.yaml/badge.svg)](https://github.com/jangruenwaldt/devops-digital-twin/actions/workflows/create_twin.yaml)

Turns DevOps system data into a single graph database using neo4j.

## Currently supported

- Building the graph
- Calculating DORA metrics: lead time, deployment frequency

## Components

- Commits of a main branch (from which releases are built)
- All releases

## Quickstart

- Copy config.json.example to config.json
- Add your neo4j connection credentials. It can be a local or cloud-hosted instance, like auraDB.
- Add your PAT from GitHub so rate limiting of GitHub API is less strict.
  The PAT can be added from [here](https://github.com/settings/tokens), and should only be given access to repositories
  you plan on using as a twin data source.  

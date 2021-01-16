from contextlib import closing
from typing import List

import psycopg2
import pymysql
import pytest
import yaml

from dbcat.catalog.metadata import Connection, Schema, Table
from dbcat.scanners.db import DbSchema

pii_data_script = """
create table no_pii(a text, b text);
insert into no_pii values ('abc', 'def');
insert into no_pii values ('xsfr', 'asawe');

create table partial_pii(a text, b text);
insert into partial_pii values ('917-908-2234', 'plkj');
insert into partial_pii values ('215-099-2234', 'sfrf');

create table full_pii(name text, location text);
insert into full_pii values ('Jonathan Smith', 'Virginia');
insert into full_pii values ('Chase Ryan', 'Chennai');

"""


pii_data_load = [
    "create table no_pii(a text, b text)",
    "insert into no_pii values ('abc', 'def')",
    "insert into no_pii values ('xsfr', 'asawe')",
    "create table partial_pii(a text, b text)",
    "insert into partial_pii values ('917-908-2234', 'plkj')",
    "insert into partial_pii values ('215-099-2234', 'sfrf')",
    "create table full_pii(name text, location text)",
    "insert into full_pii values ('Jonathan Smith', 'Virginia')",
    "insert into full_pii values ('Chase Ryan', 'Chennai')",
]

pii_data_drop = ["DROP TABLE full_pii", "DROP TABLE partial_pii", "DROP TABLE no_pii"]


def mysql_conn():
    return (
        pymysql.connect(
            host="127.0.0.1", user="piiuser", password="p11secret", database="piidb",
        ),
        Connection(
            type="mysql",
            uri="127.0.0.1",
            username="piiuser",
            password="p11secret",
            database="piidb",
        ),
        "piidb",
    )


def pg_conn():
    return (
        psycopg2.connect(
            host="127.0.0.1", user="piiuser", password="p11secret", database="piidb"
        ),
        Connection(
            type="postgres",
            uri="127.0.0.1",
            username="piiuser",
            password="p11secret",
            database="piidb",
            cluster="public",
        ),
        "public",
    )


@pytest.fixture(params=[mysql_conn(), pg_conn()])
def load_data(request):
    db_conn, extractor_conn, expected_schema = request.param
    with closing(db_conn) as conn:
        with conn.cursor() as cursor:
            for statement in pii_data_load:
                cursor.execute(statement)
            cursor.execute("commit")
        yield conn, extractor_conn, expected_schema
        with conn.cursor() as cursor:
            for statement in pii_data_drop:
                cursor.execute(statement)
            cursor.execute("commit")


def test_catalog(load_data):
    db_conn, extractor_conn, expected_schema = load_data

    scanner: DbSchema = DbSchema(connection=extractor_conn)
    catalog = scanner.scan()
    assert len(catalog.schemata) == 1

    schema: Schema = catalog.schemata[0]
    assert schema.name == expected_schema
    assert len(schema.tables) == 3

    full_pii: Table = schema.tables[0]
    no_pii: Table = schema.tables[1]
    partial_pii: Table = schema.tables[2]

    assert full_pii.name == "full_pii"
    assert no_pii.name == "no_pii"
    assert partial_pii.name == "partial_pii"

    assert full_pii.columns[0].name == "name"
    assert full_pii.columns[0].type == "text"
    assert full_pii.columns[1].name == "location"
    assert full_pii.columns[1].type == "text"


conn_config = """
connections:
  - name: pg
    type: postgres
    database: db_database
    username: db_user
    password: db_password
    port: db_port
    uri: db_uri
  - name: mys
    type: mysql
    database: db_database
    username: db_user
    password: db_password
    port: db_port
    uri: db_uri
  - name: bq
    type: bigquery
    key_path: db_key_path
    project_credentials:  db_creds
    project_id: db_project_id
  - name: gl
    type: glue
  - name: sf
    type: snowflake
    database: db_database
    username: db_user
    password: db_password
    account: db_account
    role: db_role
    warehouse: db_warehouse
"""


def test_connection_config():
    config = yaml.safe_load(conn_config)
    connections: List[Connection] = [
        Connection(**conn) for conn in config["connections"]
    ]

    assert len(connections) == 5

    # pg
    pg_connection = connections[0]
    assert pg_connection.name == "pg"
    assert pg_connection.type == "postgres"
    assert pg_connection.database == "db_database"
    assert pg_connection.username == "db_user"
    assert pg_connection.password == "db_password"
    assert pg_connection.port == "db_port"
    assert pg_connection.uri == "db_uri"

    # mysql
    mysql_conn = connections[1]
    assert mysql_conn.name == "mys"
    assert mysql_conn.type == "mysql"
    assert mysql_conn.database == "db_database"
    assert mysql_conn.username == "db_user"
    assert mysql_conn.password == "db_password"
    assert mysql_conn.port == "db_port"
    assert mysql_conn.uri == "db_uri"

    # bigquery
    bq_conn = connections[2]
    assert bq_conn.name == "bq"
    assert bq_conn.type == "bigquery"
    assert bq_conn.key_path == "db_key_path"
    assert bq_conn.project_credentials == "db_creds"
    assert bq_conn.project_id == "db_project_id"

    # glue
    glue_conn = connections[3]
    assert glue_conn.name == "gl"
    assert glue_conn.type == "glue"

    # snowflake
    sf_conn = connections[4]
    assert sf_conn.name == "sf"
    assert sf_conn.type == "snowflake"
    assert sf_conn.database == "db_database"
    assert sf_conn.username == "db_user"
    assert sf_conn.password == "db_password"
    assert sf_conn.account == "db_account"
    assert sf_conn.role == "db_role"
    assert sf_conn.warehouse == "db_warehouse"

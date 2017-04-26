# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime

# pylint: disable=import-error, unused-import
import bottle
from bottle.ext import sqlalchemy
# pylint: enable=import-error
from bottle import request
from bottle import abort
from bottle_errorsrest import ErrorsRestPlugin

from sbds.sbds_json import ToStringJSONEncoder
from sbds.server.jsonrpc import register_endpoint

from steem.steemd import Steemd
from hive.core import db_last_block
from hive.schema import metadata as hive_metadata
from sqlalchemy import create_engine

import logging
logger = logging.getLogger(__name__)

app = bottle.Bottle()
app.config['hive.DATABASE_URL'] = os.environ.get('DATABASE_URL', '')
app.config['hive.MAX_BLOCK_NUM_DIFF'] = 10
app.config['hive.MAX_DB_ROW_RESULTS'] = 100000
app.config['hive.DB_QUERY_LIMIT'] = app.config['hive.MAX_DB_ROW_RESULTS'] + 1
app.config['hive.logger'] = logger


def get_db_plugin(database_url):
    sa_engine = create_engine(database_url)
    Session.configure(bind=sa_engine)

    # pylint: disable=undefined-variable
    return sqlalchemy.Plugin(
        # SQLAlchemy engine created with create_engine function.
        sa_engine,
        # SQLAlchemy metadata, required only if create=True.
        hive_metadata,
        # Keyword used to inject session database in a route (default 'db').
        keyword='db',
        # If it is true, execute `metadata.create_all(engine)` when plugin is applied (default False).
        create=False,
        # If it is true, plugin commit changes after route is executed (default True).
        commit=False,
        # If it is true and keyword is not defined, plugin uses **kwargs argument to inject session database (default False).
        use_kwargs=False,
        create_session=Session)


app.install(
    bottle.JSONPlugin(json_dumps=lambda s: json.dumps(s, cls=ToStringJSONEncoder)))
app.install(ErrorsRestPlugin())
db_plugin = get_db_plugin(app.config['hive.DATABASE_URL'])
app.install(db_plugin)


# Non JSON-RPC routes
# -------------------
@app.get('/health')
def health(db):
    steemd = Steemd()
    last_db_block = db_last_block()
    last_irreversible_block = steemd.last_irreversible_block_num
    diff = last_irreversible_block - last_db_block
    if diff > app.config['hive.MAX_BLOCK_NUM_DIFF']:
        abort(
            500,
            'last irreversible block (%s) - highest db block (%s) = %s, > max allowable difference (%s)'
            % (last_irreversible_block, last_db_block, diff,
               app.config['hive.MAX_BLOCK_NUM_DIFF']))
    else:
        return dict(
            last_db_block=last_db_block,
            last_irreversible_block=last_irreversible_block,
            diff=diff,
            timestamp=datetime.utcnow().isoformat())


# JSON-RPC route
# --------------
jsonrpc = register_endpoint(path='/', app=app, namespace='hive')



# WSGI application
# ----------------
application = app


# dev/debug server
# ----------------
def _dev_server(port=8081, debug=True):
    # pylint: disable=bare-except
    try:
        app.run(port=port, debug=debug)
    except:
        logger.exception('HTTP Server Exception')
    finally:
        app.close()


# For pdb debug only
if __name__ == '__main__':
    _dev_server()
import os
from typing import Collection

from flask import (
    Flask, render_template, session
)

import arkhrec.helpers



def create_app(test_config=None):
    # create and configure the app

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        # DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
        # CACHE_TYPE="SimpleCache",  # Flask-Caching related configs
        # CACHE_DEFAULT_TIMEOUT=300
    )

    

    # cache=Cache(app)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import deck
    app.register_blueprint(deck.bp)

    from . import card
    app.register_blueprint(card.bp)

    from . import investigator
    app.register_blueprint(investigator.bp)

    from . import card_collection
    app.register_blueprint(card_collection.bp)

    from . import map
    app.register_blueprint(map.bp)

    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.context_processor
    def cycles_processor():
        if not arkhrec.helpers.gCycles:
            read_cycles(app)
            

        return dict(cycles=arkhrec.helpers.gCycles)

    @app.before_first_request
    def before_first_request():
        arkhrec.helpers.get_collection()

    read_cycles(app)
 
    return app

def read_cycles(app):
    import json

    with open(os.path.join(app.root_path, 'datafiles',  'cycles.json'), 'r') as f:
        cycles = json.load(f)
    with open(os.path.join(app.root_path, 'datafiles',  'packs.json'), 'r') as f:
        packs = json.load(f)
    
    arkhrec.helpers.gCycles = dict()
    for cycle in cycles:
        if cycle['code'] in arkhrec.helpers.PACKS_WITHOUT_PLAYER_CARDS:
            continue
        arkhrec.helpers.gCycles[cycle['code']] = {'code': cycle['code'], 'name': cycle['name'], 'position': cycle['position'], 'packs': []}
    for pack in packs:
        if pack['cycle_code'] in arkhrec.helpers.PACKS_WITHOUT_PLAYER_CARDS:
            continue
        arkhrec.helpers.gCycles[pack['cycle_code']]['packs'].append(pack)


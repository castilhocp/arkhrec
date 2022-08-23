import os

from flask import (
    Flask, render_template
)


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

    from . import map
    app.register_blueprint(map.bp)

    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app
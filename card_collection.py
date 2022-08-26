from flask import current_app
import os

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

bp = Blueprint('card_collection', __name__, url_prefix='/collection')

import arkhrec.general_helpers

@bp.route('/update', methods=['POST'])
def update():
    card_collection = dict()
    
    for k,v in request.form.items():
        card_collection[k] = v
    
    session['card_collection'] = card_collection
    if request.method == 'POST':
        return redirect(request.referrer or url_for('index'))

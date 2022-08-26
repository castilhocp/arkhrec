import functools
from flask import current_app
import os

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('deck', __name__, url_prefix='/deck')

import arkhrec.deck_builder
import arkhrec.general_helpers
import arkhrec.data_helpers

@bp.route('/', methods=['GET', 'POST'])
def search():
    
    if request.method == 'POST':
        return redirect(url_for('deck.view', deck_id=request.form['deck_id']))
    return render_template('deck/search.html')

@bp.route('/<int:deck_id>', methods=['GET'])
def view(deck_id):
    
    import requests
    import pandas as pd

    # Read deck from ArkhamDB
    # deck_id = '2103914'
    deck_url = "http://arkhamdb.com/api/public/deck/"
    try:
        status_code = requests.get(deck_url+str(deck_id), verify=False)
    except  requests.exceptions.RequestException as e:
        flash('Failed to fetch deck data from ArkhamDB')
        return redirect(url_for('deck.search'))
    if (not status_code.ok) or (status_code.headers['Content-Type'] != 'application/json'):
        flash('Failed to fetch deck data from ArkhamDB')
        return redirect(url_for('deck.search'))
    
    # Read the deck from ArkhamDB's response
    deck_to_compare = pd.read_json("["+status_code.text+"]", orient='records')

    # Remove duplicate cards and substitute code for the "principal" copy    
    [cards_in_deck, cards_not_in_deck, deck_to_compare_sub] = arkhrec.deck_builder.get_recommendations_for_deck(deck_to_compare)
    deck_statistics = arkhrec.deck_builder.calculate_deck_statistics(deck_to_compare_sub)
    deck_info = arkhrec.deck_builder.get_deck_info(deck_to_compare, cards_in_deck)    

    return render_template('deck/view.html', cards_in_deck=cards_in_deck.to_dict('index'), cards_not_in_deck=cards_not_in_deck.to_dict('index'), deck_statistics=deck_statistics, deck_info=deck_info)


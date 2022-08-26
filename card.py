from flask import session

import arkhrec.general_helpers
import arkhrec.data_helpers as cd
import pandas as pd

from flask import (
    Blueprint, redirect, render_template, request, url_for, g 
)

bp = Blueprint('card', __name__, url_prefix='/card')

import numpy as np

@bp.route('/', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        
        return redirect(url_for('card.view', card_id=request.form['card_id']))

    analysed_cards = cd.get_analysed_cards()
    
    return render_template('card/search.html', cards=analysed_cards.to_dict(orient='index'))

@bp.route('/<card_id>', methods=['GET'])
def view(card_id):    

    # Gets occurrence, cooccurrence and cooccurrence ratio for cards in collection
    card_similarities = cd.get_similarities_with_card(card_id)
    filtered_card_similarities = cd.filter_cards_in_collection(card_similarities, [card_id])

    # Gets presence, occurrence for all investigators
    usage_by_investigators = cd.get_usage_by_investigators(card_id)

    num_of_decks = len(cd.get_all_decks())
    num_of_cards = len(cd.get_analysed_card_codes())

    return render_template('card/view.html', card_id=card_id, card_info=filtered_card_similarities.to_dict(orient='index'), investigators=usage_by_investigators.to_dict(orient='index'), num_of_decks=num_of_decks, num_of_cards=num_of_cards)
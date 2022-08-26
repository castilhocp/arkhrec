from dataclasses import asdict
from flask import current_app
import os
from arkhrec.deck_builder import build_average_deck
import arkhrec.general_helpers
import arkhrec.data_helpers as cd
import math

from flask import (
    Blueprint, redirect, render_template, request, url_for
)

bp = Blueprint('investigator', __name__, url_prefix='/investigator')

@bp.route('/', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        
        return redirect(url_for('investigator.view', investigator_id=request.form['investigator_id'])) 

    num_of_decks = len(cd.get_all_decks())
    investigators = cd.get_all_investigators('code_str')
      
    return render_template('investigator/search.html', investigators=investigators.to_dict(orient='index'),num_of_decks=num_of_decks)

@bp.route('/<investigator_id>', methods=['GET'])
def view(investigator_id):
    investigators = cd.get_all_investigators()

    investigator = investigators.loc[investigator_id].to_frame().transpose()
    investigator['text_icons'] = arkhrec.general_helpers.convert_text_to_icons(investigator['text'][0])

    num_of_decks = len(cd.get_all_decks())
    num_of_investigators = len(investigators)

    investigator_cards_usage = cd.get_investigator_cards_usage(investigator)

    deck_statistics = cd.get_investigator_deck_statistics(investigator)

    [average_deck, card_reqs] = build_average_deck(investigator, investigator_cards_usage, deck_statistics)
    
    investigator_cards_usage = investigator_cards_usage.drop(card_reqs['code_str'], errors='ignore')
    filtered_investigator_cards_usage = cd.filter_cards_in_collection(investigator_cards_usage)
    
    return render_template('investigator/view.html', investigator_info=investigator.to_dict(orient='index'), investigator_id=investigator_id, card_info=filtered_investigator_cards_usage.to_dict(orient='index'), num_of_decks=num_of_decks, num_of_investigators=num_of_investigators, deck_statistics=deck_statistics, average_deck = average_deck.to_dict(orient='index'), average_deck_size = average_deck['amount'].sum(), average_deck_xp = average_deck['total_xp'].sum())





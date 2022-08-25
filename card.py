from flask import current_app
from flask import session
import os
import arkhrec.helpers
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

    analysed_cards = get_analysed_cards()
    
    return render_template('card/search.html', cards=analysed_cards.to_dict(orient='index'))

@bp.route('/<card_id>', methods=['GET'])
def view(card_id):    

    # Gets occurrence, cooccurrence and cooccurrence ratio for cards in collection
    card_similarities = get_similarities_with_card(card_id)
    filtered_card_similarities = filter_cards_in_collection(card_similarities, [card_id])

    # Gets presence, occurrence for all investigators
    usage_by_investigators = get_usage_by_investigators(card_id)

    num_of_decks = len(get_all_decks())
    num_of_cards = len(get_analysed_card_codes())

    return render_template('card/view.html', card_id=card_id, card_info=filtered_card_similarities.to_dict(orient='index'), investigators=usage_by_investigators.to_dict(orient='index'), num_of_decks=num_of_decks, num_of_cards=num_of_cards)

# This function returns a list of all cards with calculated cooccurrences
# Returns a Pandas Dataframe with:
#  - Index:         'code_str' -> string formatted card code (5 digits)
#  - Columns:       
def get_analysed_cards():
    all_cards = get_all_cards()
    analysed_card_codes = get_analysed_card_codes()
    card_cooc = get_card_cooccurrences()

    all_cards = all_cards.set_index('code_str')
    analysed_cards = all_cards.merge(analysed_card_codes, left_index=True, right_index=True)

    tuples = list(zip(card_cooc.index, card_cooc.index))
    card_cooc_stacked = card_cooc.stack()[tuples]
    analysed_cards = analysed_cards.join(card_cooc_stacked.to_frame('Occurrences').reset_index(level=[0]))
    analysed_cards['occurrences_rank'] = analysed_cards['Occurrences'].rank(method="max", ascending=False)

    analysed_cards = convert_xp_to_str(analysed_cards)
    analysed_cards = set_color(analysed_cards)

    analysed_cards = analysed_cards.fillna("-")

    analysed_cards.loc[:,'text_icons'] = analysed_cards['text'].apply(arkhrec.helpers.convert_text_to_icons)
    
    analysed_cards['cycle'] = analysed_cards.apply(arkhrec.helpers.set_cycle, axis=1)

    analysed_cards = analysed_cards.drop('01000')
    
    return analysed_cards

def get_analysed_decks():
    analysed_decks = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))
    return analysed_decks

def get_similarities_with_card(card_id):
    analysed_cards = get_analysed_cards()
    card_cooc = get_card_cooccurrences()
    card_jaccard_score = get_card_jaccard_scores()

    cooc_with_card = card_cooc[card_id].to_frame('Cooccurrences')
    
    selected_card_jaccard_scores = card_jaccard_score[card_id].to_frame()
    selected_card_jaccard_scores.columns = ['Jaccard Score']
    selected_card_jaccard_scores.loc[:,'Jaccard Score'] = selected_card_jaccard_scores.applymap(lambda x: "{:0.0%}".format(x))

    analysed_cards_with_similarities = analysed_cards.join(selected_card_jaccard_scores).join(cooc_with_card)

    return analysed_cards_with_similarities

def get_usage_by_investigators(card_id):
    inv_cooc_ratio = get_card_investigator_cooccurrences()
    all_decks = get_all_decks()
    investigators = get_all_investigators()

    usage_by_investigators = inv_cooc_ratio[card_id].to_frame()
    usage_by_investigators.columns = ['Coocurrence']
    usage_by_investigators.loc[:,'Coocurrence'] = usage_by_investigators.applymap(lambda x: "{:0.0%}".format(x))   

    number_of_decks_per_investigator = all_decks.groupby('investigator_name').count()['id'].to_frame()
    number_of_decks_per_investigator.columns = ['number_of_decks']
    
    usage_by_investigators = usage_by_investigators.join(investigators[['faction_code', 'code_str']])
    usage_by_investigators['color'] = usage_by_investigators['faction_code']
    usage_by_investigators = usage_by_investigators.join(number_of_decks_per_investigator)

    usage_by_investigators.index.name = 'investigator_name'
    usage_by_investigators = usage_by_investigators.reset_index().set_index('code_str')
    usage_by_investigators['cycle'] = usage_by_investigators.apply(arkhrec.helpers.set_cycle, axis=1)
    usage_by_investigators = usage_by_investigators.reset_index().set_index('investigator_name')

    return usage_by_investigators

def filter_cards_in_collection(cards_to_filter, other_cards_to_include=[]):
    all_cards = get_all_cards()
    all_cards.loc[:,'unique_code'] = all_cards.loc[:, 'code_str']
    all_cards.loc[~all_cards['duplicate_of'].isna(), 'unique_code'] = all_cards.loc[~all_cards['duplicate_of'].isna(), 'duplicate_of'].astype(int).astype(str).apply(str.zfill, args=[5])
    card_collection = arkhrec.helpers.get_collection()
    card_collection_codes = all_cards[all_cards['pack_code'].isin(card_collection.keys())]['unique_code'].unique()
    card_collection_codes = np.append(card_collection_codes, other_cards_to_include)
    filtered_cards = cards_to_filter.loc[cards_to_filter.index.intersection(card_collection_codes)]

    return filtered_cards

def get_all_investigators():
    all_cards = get_all_cards()
    all_investigators = all_cards[all_cards['type_code']=="investigator"]
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'])
    investigator_unique_codes = all_investigators.groupby('name')['code'].min()
    all_cards.loc[:,'code'] = pd.to_numeric(all_cards['code'], errors='coerce')
    investigators = all_cards[all_cards['code'].isin(investigator_unique_codes.values)].set_index('name')
    return investigators

def convert_xp_to_str(cards):
    cards.loc[:,'xp_text'] = cards.loc[:,'xp'].to_frame().applymap(lambda x: "{:0.0f}".format(x) if x>0 else '')
    return cards

def set_color(cards):
    cards['color'] = cards['faction_code']
    cards.loc[cards['faction2_code'].notna(),'color']='multi'
    return cards

def get_all_cards():
    if 'all_cards' not in g:
        g.all_cards = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    
    return g.all_cards

def get_all_decks():
    if 'all_decks' not in g:
        g.all_decks = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))

    return g.all_decks

def get_analysed_card_codes():
    if 'analysed_card_codes' not in g:
        g.analysed_card_codes = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))

    return g.analysed_card_codes

def get_card_cooccurrences():
    if 'card_cooccurrences' not in g:
        g.card_cooccurrences = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cooc.pickle'))

    return g.card_cooccurrences

def get_card_jaccard_scores():
    if 'card_jaccard_scores' not in g:
        g.card_jaccard_scores = card_jaccard_score = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_jaccard_score.pickle'))
    
    return g.card_jaccard_scores

def get_card_investigator_cooccurrences():
    if 'card_investigator_cooccurrences' not in g:
        g.card_investigator_cooccurrences = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'inv_cooc_ratio.pickle'))

    return g.card_investigator_cooccurrences

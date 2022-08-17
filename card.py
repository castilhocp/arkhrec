from lib2to3.pytree import convert
from flask import current_app
import os
import arkhrec.helpers

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('card', __name__, url_prefix='/card')

@bp.route('/', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        
        return redirect(url_for('card.view', card_id=request.form['card_id']))

    import pandas as pd

    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    # duplicates = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'duplicates.pickle'))
    card_frequencies_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))
    card_cooc = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cooc.pickle'))
    all_decks_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))
    num_of_decks = len(all_decks_clean)
    tuples = list(zip(card_cooc.index, card_cooc.index))
    card_cooc_stacked = card_cooc.stack()[tuples]

    card_cycles_clean = card_cycles.set_index('code_str')
    card_cycles_clean = card_cycles_clean.merge(card_frequencies_clean, left_index=True, right_index=True)
    card_cycles_clean = convert_xp_to_str(card_cycles_clean)
    card_cycles_clean['color'] = card_cycles_clean['faction_code']
    card_cycles_clean.loc[card_cycles_clean['faction2_code'].notna(),'color']='multi'
    card_cycles_clean = card_cycles_clean.join(card_cooc_stacked.to_frame('Uses').reset_index(level=[0]))
    card_cycles_clean = card_cycles_clean.fillna("-")
    card_cycles_clean = card_cycles_clean.drop('01000')
    
    
    
    return render_template('card/search.html', cards=card_cycles_clean.to_dict(orient='index'),num_of_decks=num_of_decks)

@bp.route('/<card_id>', methods=['GET'])
def view(card_id):
    import pandas as pd
    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    card_jaccard_score = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_jaccard_score.pickle'))
    inv_cooc_ratio = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'inv_cooc_ratio.pickle'))
    card_frequencies_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))
    all_decks_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))
    card_cooc = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cooc.pickle'))
    tuples = list(zip(card_cooc.index, card_cooc.index))
    card_cooc_stacked = card_cooc.stack()[tuples].to_frame('Occurrences').reset_index(level=[0])
    cooc_with_card = card_cooc[card_id].to_frame('Cooccurrences')
    

    num_of_decks = len(all_decks_clean)
    num_of_cards = len(card_frequencies_clean)

    selected_card_jaccard_scores = card_jaccard_score[card_id].to_frame()
    selected_card_jaccard_scores.columns = ['Jaccard Score']
    selected_card_jaccard_scores.loc[:,'Jaccard Score'] = selected_card_jaccard_scores.applymap(lambda x: "{:0.0%}".format(x))
    selected_card_inv_cooc = inv_cooc_ratio[card_id].to_frame()
    selected_card_inv_cooc.columns = ['Coocurrence']
    selected_card_inv_cooc.loc[:,'Coocurrence'] = selected_card_inv_cooc.applymap(lambda x: "{:0.0%}".format(x))
    all_investigators = card_cycles[card_cycles['type_code']=="investigator"]
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'])
    investigator_unique_codes = all_investigators.groupby('name')['code'].min()
    card_cycles.loc[:,'code'] = pd.to_numeric(card_cycles['code'], errors='coerce')
    investigators = card_cycles[card_cycles['code'].isin(investigator_unique_codes.values)].set_index('name')

    number_of_decks_per_investigator = all_decks_clean.groupby('investigator_name').count()['id'].to_frame()
    number_of_decks_per_investigator.columns = ['number_of_decks']
    
    selected_card_inv_cooc = selected_card_inv_cooc.join(investigators[['faction_code', 'code_str']])
    selected_card_inv_cooc['color'] = selected_card_inv_cooc['faction_code']
    selected_card_inv_cooc = selected_card_inv_cooc.join(number_of_decks_per_investigator)

    card_cycles_clean = card_cycles.set_index('code_str')
    card_cycles_clean = card_cycles_clean.merge(card_frequencies_clean, left_index=True, right_index=True)
    card_cycles_clean = card_cycles_clean.join(selected_card_jaccard_scores)
    card_cycles_clean.loc[:,'xp_text'] = card_cycles_clean['xp']
    card_cycles_clean = convert_xp_to_str(card_cycles_clean)
    card_cycles_clean['color'] = card_cycles_clean['faction_code']
    card_cycles_clean.loc[card_cycles_clean['faction2_code'].notna(),'color']='multi'
    card_cycles_clean = card_cycles_clean.join(card_cooc_stacked).join(cooc_with_card)
    card_cycles_clean['occurrences_rank'] = card_cycles_clean['Occurrences'].rank(method="max", ascending=False)
    
    card_cycles_clean = card_cycles_clean.fillna("-")
    card_cycles_clean = card_cycles_clean.drop('01000')

    card_cycles_clean.loc[:,'text_icons'] = card_cycles_clean['text'].apply(arkhrec.helpers.convert_text_to_icons)
    

    return render_template('card/view.html', card_id=card_id, card_info=card_cycles_clean.to_dict(orient='index'), investigators=selected_card_inv_cooc.to_dict(orient='index'), num_of_decks=num_of_decks, num_of_cards=num_of_cards)

def convert_xp_to_str(cards):
    cards.loc[:,'xp'] = cards.loc[:,'xp'].to_frame().applymap(lambda x: "{:0.0f}".format(x) if x>0 else '')
    return cards
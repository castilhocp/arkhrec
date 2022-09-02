from dataclasses import asdict
import functools
from flask import current_app
import os
import html

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

bp = Blueprint('map', __name__, url_prefix='/map')

@bp.route('/decks', methods=['GET'])
def deck_map():
    
    import pandas as pd

    
    all_decks_view = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_view.pickle'))
    investigator_summary_view = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'investigator_summary_view.pickle'))
    # print(all_decks_view.iloc[0,:].to_json())
    # print("Exiting for")
    return render_template('map/deck.html', all_decks = all_decks_view.to_json(), investigator_summary=investigator_summary_view.to_json())

def build_investigator_pickle_files():
    import pandas as pd
    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    card_cycles = card_cycles.set_index('code_str')
    
    inv_cooc_ratio = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'inv_cooc_ratio.pickle'))
    all_decks_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))
    card_frequencies_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))
    card_cooc = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cooc.pickle'))
    investigator_jaccards = pd.read_csv(os.path.join(current_app.root_path, 'datafiles',  'investigator_jaccards.csv'))

    num_of_decks = len(all_decks_clean)

    all_decks_view = all_decks_clean[['id', 'date_creation']].set_index('id')


    all_decks_view.loc[:,'name'] = all_decks_clean.set_index('id')['name'].apply(html.escape)
    all_decks_view.loc[:,'investigator_name'] = all_decks_clean.set_index('id')['investigator_name'].apply(html.escape)

    card_cycles_clean = card_cycles.set_index('code_str')

    # Keeps only the cards that have cooccurrences calculates
    card_cycles_clean = card_cycles_clean.merge(card_frequencies_clean, left_index=True, right_index=True)

    # Joins the number of occurrences of each card
    # Uses pandas multiindex to facilitate retrieving the data
    # This basically transforms a 2x2 matrix in a "database" style
    tuples = list(zip(card_cooc.index, card_cooc.index))
    card_cooc_stacked = card_cooc.stack()[tuples].to_frame('occurrences').reset_index(level=[0])
    card_cycles_clean = card_cycles_clean.join(card_cooc_stacked)

    # Cleans the XP value for visualization    
    card_cycles_clean.loc[:,'xp_text'] = card_cycles_clean['xp']
    card_cycles_clean.loc[:,'xp_text'] = card_cycles_clean.loc[:,'xp_text'].to_frame().applymap(lambda x: " ({:0.0f})".format(x) if x>0 else '')
    card_cycles_clean.loc[:,'exhib_name'] = card_cycles_clean['name'] + card_cycles_clean['xp_text']

    # Calculates the synergy with investigator
    card_cycles_clean['card_occurrences_ratio'] = card_cycles_clean['occurrences'] / num_of_decks

    inv_cooc_ratio_no_reqs = inv_cooc_ratio.loc[:,card_cycles_clean['restrictions'].isna()].drop('01000', axis=1)   
    synergy = pd.DataFrame(inv_cooc_ratio_no_reqs.values - card_cycles_clean.loc[inv_cooc_ratio_no_reqs.columns, 'card_occurrences_ratio'].values, columns=inv_cooc_ratio_no_reqs.columns, index = inv_cooc_ratio_no_reqs.index)

    import numpy as np
    # Gets top 5 synergies
    N = 5
    cols = synergy.columns.tolist()
    # print(cols)
    a = synergy[cols].to_numpy().argsort()[:, :-N-1:-1]
    c = np.array(cols)[a]
    d = synergy[cols].to_numpy()[np.arange(a.shape[0])[:, None], a]
    df1 = pd.DataFrame(c).rename(columns=lambda x : f'max_{x+1}_card_code')
    df2 = pd.DataFrame(d).rename(columns=lambda x : f'max_{x+1}_synergy')
    c = synergy.columns.tolist() + [y for x in zip(df2.columns, df1.columns) for y in x]

    investigator_summary = pd.concat([df1,df2],axis=1)
    investigator_summary.index = synergy.index

    
    for i in range(1,6):
        investigator_summary = investigator_summary.join(card_cycles_clean['exhib_name'], on='max_{}_card_code'.format(i)).rename(columns={"exhib_name":"max_{}_exhib_name".format(i)})

    investigator_jaccards = pd.read_csv('investigator_jaccards.csv', delimiter=';', decimal=',')
    investigator_summary.join(investigator_jaccards.set_index(['inv1', 'inv2'])['average_jaccard'], on=['investigator_name', 'investigator_name']).rename(columns={"average_jaccard":"self_jaccard"})
    
    top_inv2 = investigator_jaccards.rename(columns={"inv1":"inv2", "inv2":"inv1"})
    top_similarities = pd.concat([investigator_jaccards, top_inv2]).sort_values(['inv1', 'average_jaccard'], ascending=[True,False]).groupby(level=0)
    top_similarities = top_similarities.query("inv1!=inv2")
    pivot = pd.pivot_table(top_similarities, index='inv1', columns='inv2',values=['average_jaccard']).fillna(0)
    pivot.columns = pivot.columns.droplevel(0)
    N = 5
    cols = pivot.columns.tolist()
    # print(cols)
    a = pivot[cols].to_numpy().argsort()[:, :-N-1:-1]
    c = np.array(cols)[a]
    d = pivot[cols].to_numpy()[np.arange(a.shape[0])[:, None], a]
    df1 = pd.DataFrame(c).rename(columns=lambda x : f'max_{x+1}_similar_inv')
    df2 = pd.DataFrame(d).rename(columns=lambda x : f'max_{x+1}_jaccard')
    c = pivot.columns.tolist() + [y for x in zip(df2.columns, df1.columns) for y in x]
    most_similar_investigators = pd.concat([df1,df2],axis=1)
    most_similar_investigators.index = pivot.index

    investigator_summary_export = investigator_summary.join(most_similar_investigators)

    all_investigators = card_cycles[card_cycles['type_code']=="investigator"]
    

    # There are investigators with multiple codes (e.g. parallel versions, book versions, etc.)
    # Gets the minimum code (that's the "cycle" version)
    # Converts to numeric to find the minimum value
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'])
    investigator_unique_codes = all_investigators.groupby('name')['code'].min() 
    card_cycles.loc[:,'code'] = pd.to_numeric(card_cycles['code'], errors='coerce')
    card_cycles['color'] = card_cycles['faction_code']
    card_cycles.loc[~card_cycles['faction2_code'].isna(),'color']='multi'
    investigators = card_cycles[card_cycles['code'].isin(investigator_unique_codes.values)].set_index('name')

    investigator_summary_export = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'investigator_summary_export.pickle'))

    investigator_summary_export.join(investigators[['faction_code', 'code_str']])

    investigator_summary_view = pd.DataFrame(index=investigator_summary_export.index)    

    for investigator_name, investigator_info in investigator_summary_export.iterrows():
        print(investigator_name,flush=True)
        similar_cards_html = "<h4>Distinctive cards</h4><ol>"
        similar_investigators_html = "<h4>Most similar investigators</h4><ol>"
        for i in range(1,6):
            similar_investigators_html += "<li>"
            similar_inv_name = investigator_info["max_{}_similar_inv".format(i)]
            similar_inv_faction = investigators.loc[similar_inv_name,'faction_code']
            similar_inv_code = investigators.loc[similar_inv_name,'code_str']
            if similar_inv_faction in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    similar_investigators_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(similar_inv_faction, similar_inv_faction)
            similar_investigators_html += "<a href=\\\"{}\\\" class=\\\"{}\\\">{}</a></li>".format(url_for('investigator.view', investigator_id=similar_inv_code), similar_inv_faction, html.escape(similar_inv_name))

            similar_cards_html += "<li>"
            similar_card_name = investigator_info["max_{}_exhib_name".format(i)]
            similar_card_code = investigator_info["max_{}_card_code".format(i)]
            similar_card_faction1 = card_cycles.set_index('code_str').loc[similar_card_code,'faction_code']
            similar_card_faction2 = card_cycles.set_index('code_str').loc[similar_card_code,'faction2_code']
            similar_card_faction3 = card_cycles.set_index('code_str').loc[similar_card_code,'faction3_code']
            similar_card_color = card_cycles.set_index('code_str').loc[similar_card_code,'color']
            if similar_card_faction1 in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    similar_cards_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(similar_card_faction1, similar_card_faction1)
            if similar_card_faction2 in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    similar_cards_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(similar_card_faction2, similar_card_faction2)
            if similar_card_faction3 in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    similar_cards_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(similar_card_faction3, similar_card_faction3)
            similar_cards_html += "<a href=\\\"{}\\\" class=\\\"{}\\\">{}</a></li>".format(url_for('card.view', card_id=similar_card_code), similar_card_color, html.escape(similar_card_name))
        similar_cards_html += "</ol>"
        similar_investigators_html += "</ol>"

        investigator_summary_view.loc[investigator_name,'similar_cards_html'] = similar_cards_html
        investigator_summary_view.loc[investigator_name,'similar_investigators_html'] = similar_investigators_html

    investigator_summary_view = investigator_summary_view.reset_index()
    # print(investigator_summary_view)
    investigator_summary_view.loc[:,'investigator_name'] = investigator_summary_view.reset_index()['investigator_name'].apply(html.escape)
    # print(investigator_summary_view)
    investigator_summary_view = investigator_summary_view.set_index('investigator_name')
    # print(investigator_summary_view)
    investigator_summary_view.to_pickle(os.path.join(current_app.root_path, 'datafiles',  'investigator_summary_view.pickle'))


    for index, deck in all_decks_clean.iterrows():
        # print(deck['name'])
        df_deck = pd.DataFrame().from_dict(deck['slots'], orient='index', columns=['quantity'])
        df_deck = df_deck.join(card_cycles.set_index('code_str'), rsuffix='_card')[['name', 'quantity', 'type_code', 'faction_code', 'faction2_code', 'faction3_code', 'xp']]
        df_deck['color'] = df_deck['faction_code']
        df_deck.loc[~df_deck['faction2_code'].isna(),'color']='multi'
        def sort_faction(row):            
            return {
                "guardian": "1",
                "mystic": "2",
                "seeker": "3",
                "rogue": "4",
                "survivor": "5",
                "multi":"6",
                "neutral": "7"
            }.get(row['color'],"other")
        df_deck['faction_sort'] = df_deck.apply(sort_faction, axis=1)
        df_deck = df_deck.sort_values(['type_code', 'faction_sort', 'name'])
        deck_html = '<ul style=\\"font-size:small\\">'
        asset_line=0
        event_line=0
        skill_line=0
        treachery_line=0
        enemy_line=0
        for card_id, card in df_deck.iterrows():
            if asset_line==0 and card['type_code']=='asset':
                deck_html+="<h6>Assets</h6>"
                asset_line = 1
            if event_line==0 and card['type_code']=='event':
                deck_html+="<h6>Events</h6>"
                event_line = 1
            if skill_line==0 and card['type_code']=='skill':
                deck_html+="<h6>Skills</h6>"
                skill_line = 1
            if treachery_line==0 and card['type_code']=='treachery':
                deck_html+="<h6>Treacheries</h6>"
                treachery_line = 1
            if enemy_line==0 and card['type_code']=='enemy':
                deck_html+="<h6>Enemies</h6>"
                enemy_line = 1
            deck_html += "<li>{}x".format(card['quantity'])
            if not pd.isna(card['faction2_code']):
                color = 'multi'
            else:
                color = card['faction_code']
            if card['faction_code'] in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    deck_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(card['faction_code'], card['faction_code'])
            if card['faction2_code'] in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    deck_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(card['faction2_code'], card['faction2_code'])
            if card['faction3_code'] in ['mystic', 'guardian', 'rogue', 'survivor', 'seeker']:
                    deck_html += "<span class=\\\"icon icon-{}\\\" title=\\\"{}\\\"></span>".format(card['faction3_code'], card['faction3_code'])
            deck_html += "<a href=\\\"{}\\\" class=\\\"{}\\\">{}</a></li>".format(url_for('card.view', card_id=card_id), color, html.escape(card['name']))
        # deck['deck_html'] = deck_html
        # print(deck_html)
        all_decks_view.loc[deck['id'], 'deck_html'] = deck_html

    all_decks_view.to_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_view.pickle'))
    investigator_summary_view.to_pickle(os.path.join(current_app.root_path, 'datafiles',  'investigator_summary_view.pickle'))
from flask import g
from flask import current_app
import os
import pandas as pd
import numpy as np
import pdb

import arkhrec.general_helpers

gCycles=dict()

PACKS_WITHOUT_PLAYER_CARDS = ['promotional', 'parallel', 'side_stories']

def get_all_cards():
    if 'all_cards' not in g:
        all_cards = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_cards.pickle'))
        all_cards.loc[:,'unique_code'] = all_cards.loc[:, 'code_str']
        all_cards.loc[~all_cards['duplicate_of'].isna(), 'unique_code'] = all_cards.loc[~all_cards['duplicate_of'].isna(), 'duplicate_of'].astype(int).astype(str).apply(str.zfill, args=[5])
        g.all_cards=all_cards

    return g.all_cards

def get_all_decks():
    if 'all_decks' not in g:
        g.all_decks = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))

    return g.all_decks

def get_analysed_card_frequencies():
    if 'analysed_card_frequencies' not in g:
        g.analysed_card_frequencies = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'analysed_card_frequencies.pickle'))

    return g.analysed_card_frequencies

def get_card_cooccurrences():
    if 'card_cooccurrences' not in g:
        g.card_cooccurrences = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'cooccurrences_calculated.pickle'))

    return g.card_cooccurrences

def get_card_investigator_cooccurrences():
    if 'card_investigator_cooccurrences' not in g:
        g.card_investigator_cooccurrences = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'inv_cooccurrences_calculated.pickle'))

    return g.card_investigator_cooccurrences

def get_collection():
    from flask import session

    if 'card_collection' in session:
        return session['card_collection']

    card_collection = dict()
    
    for cycle in gCycles:
        

        if gCycles[cycle]['code'] in PACKS_WITHOUT_PLAYER_CARDS:
            continue
        for pack in gCycles[cycle]['packs']:
            card_collection[pack['code']] = True

    session['card_collection'] = card_collection
    return session['card_collection']

def get_all_investigators(index='code_str'):
    if 'all_investigators'  in g:
        return g.all_investigators

    all_cards = get_all_cards()
    all_decks = get_all_decks()

    all_investigators = all_cards[all_cards['type_code']=="investigator"]

    # There are investigators with multiple codes (e.g. parallel versions, book versions, etc.)
    # Gets the minimum code (that's the "cycle" version)
    # Converts to numeric to find the minimum value
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'], errors='coerce')
    investigator_unique_codes = all_investigators.groupby('name')['code'].min()
    all_cards.loc[:,'code'] = pd.to_numeric(all_cards['code'], errors='coerce')
    investigators = all_cards[all_cards['code'].isin(investigator_unique_codes.values)].set_index('name')

    # total number of decks in database
    number_of_decks_per_investigator = all_decks.groupby('investigator_name').count()['id'].to_frame()
    number_of_decks_per_investigator.columns = ['number_of_decks']
    investigators = investigators.join(number_of_decks_per_investigator)

    # gets rank between all investigators
    investigators['occurrences_rank'] = investigators['number_of_decks'].rank(method="max", ascending=False)
    
    # creates string for faction color - really useless since there is no "multi" colored investigator
    investigators = arkhrec.general_helpers.set_color(investigators)
    
    # removes investigators with no decks (currently, only the ones from the TCU prologue)
    investigators = investigators.fillna("-")
    investigators = investigators[investigators['number_of_decks']!='-']

    #removes duplicates (Hank Samson)
    investigators = investigators[investigators['code']!='-']
    investigators = investigators.reset_index()
    investigators.rename(columns={'index':'name'}, inplace=True)

    investigators = investigators.set_index(index)

    g.all_investigators = investigators

    return g.all_investigators

# This function returns a list of all cards with calculated cooccurrences
# Returns a Pandas Dataframe with:
#  - Index:         'code_str' -> string formatted card code (5 digits)
#  - Columns:       
def get_analysed_cards():
    all_cards = get_all_cards()
    analysed_card_codes = get_analysed_card_frequencies()
    # card_cooc = get_card_cooccurrences()
    all_cards = all_cards.set_index('code_str')
    analysed_cards = all_cards.merge(analysed_card_codes, left_index=True, right_index=True)

    analysed_cards['appearances'] = analysed_cards['appearances'].astype(int)
    analysed_cards['appearances_rank'] = analysed_cards['appearances'].rank(method="max", ascending=False)

    analysed_cards = arkhrec.general_helpers.convert_xp_to_str(analysed_cards)
    analysed_cards = arkhrec.general_helpers.set_color(analysed_cards)

    analysed_cards = analysed_cards.fillna("-")

    analysed_cards.loc[:,'text_icons'] = analysed_cards['text'].apply(arkhrec.general_helpers.convert_text_to_icons)
    
    analysed_cards['cycle'] = analysed_cards.apply(arkhrec.general_helpers.set_cycle, axis=1)

    analysed_cards = analysed_cards.drop('01000')
    
    return analysed_cards

def get_similarities_with_card(card_id):
    analysed_cards = get_analysed_cards()
    card_cooc = get_card_cooccurrences()
 
    c1 = card_cooc.xs(card_id, level=1).drop('occurrences_card2', axis=1).rename(columns={'occurrences_card1':'occurrences'})
    c2 = card_cooc.xs(card_id, level=0).drop('occurrences_card1', axis=1).rename(columns={'occurrences_card2':'occurrences'})
    c = pd.concat([c1,c2])

    analysed_cards_with_similarities = analysed_cards.join(c)
    analysed_cards_with_similarities = analysed_cards_with_similarities[~analysed_cards_with_similarities.index.duplicated()]
    analysed_cards_with_similarities = analysed_cards_with_similarities.dropna()
    analysed_cards_with_similarities.loc[:,'jaccard'] = analysed_cards_with_similarities['jaccard'].apply(lambda x: "{:0.0%}".format(x))   
    analysed_cards_with_similarities.loc[:,'cost_view'] = analysed_cards_with_similarities['cost'].apply(lambda x: x if (x=='' or x=='X' or x=='x' or x=='-') else "{:0.0f}".format(float(x)))
    analysed_cards_with_similarities = analysed_cards_with_similarities.dropna()

    return analysed_cards_with_similarities

def filter_cards_in_collection(cards_to_filter, other_cards_to_include=[]):
    all_cards = get_all_cards()
    
    card_collection = get_collection()
    card_collection_codes = all_cards[all_cards['pack_code'].isin(card_collection.keys())]['unique_code'].unique()
    card_collection_codes = np.append(card_collection_codes, other_cards_to_include)
    filtered_cards = cards_to_filter.loc[cards_to_filter.index.intersection(card_collection_codes)]

    return filtered_cards  

def get_usage_by_investigators(card_id):
    inv_cooc = get_card_investigator_cooccurrences()
    investigators = get_all_investigators()

    usage_by_investigators = inv_cooc.xs(card_id,level=1)
    usage_by_investigators = usage_by_investigators.rename(columns={'cooccurrence':'Coocurrence', 'occurrences_investigator': 'number_of_decks'})
    usage_by_investigators.loc[:,'presence'] = usage_by_investigators['presence'].apply(lambda x: "{:0.0%}".format(x))   
    
    usage_by_investigators = usage_by_investigators.join(investigators[['name', 'faction_code', 'faction2_code']])
    usage_by_investigators = arkhrec.general_helpers.set_color(usage_by_investigators)

    usage_by_investigators = usage_by_investigators.reset_index().set_index('investigator')
    usage_by_investigators['cycle'] = usage_by_investigators.apply(arkhrec.general_helpers.set_cycle, axis=1)
    usage_by_investigators = usage_by_investigators.reset_index().set_index('name')
    usage_by_investigators.index.name = 'investigator_name'
    usage_by_investigators = usage_by_investigators.dropna()


    return usage_by_investigators

def get_investigator_cards_usage(investigator):
    analysed_cards = get_analysed_cards()
    inv_cooc = get_card_investigator_cooccurrences()

    # Joins the number of cooccurrences of each card with this investigator
    inv_card_cooccurrences = inv_cooc.loc[investigator.index].droplevel('investigator')
    print(inv_card_cooccurrences)
    investigator_cards_usage = analysed_cards.join(inv_card_cooccurrences)

    investigator_cards_usage = investigator_cards_usage.dropna()

    return investigator_cards_usage

def get_duplicates_unique_code():
    all_cards = get_all_cards()
    duplicates = all_cards.loc[~all_cards['duplicate_of'].isna(), ['code_str', 'unique_code']].set_index('code_str')
    
    return duplicates

def get_investigator_deck_statistics(investigator):
    all_decks = get_all_decks()
    investigators = get_all_investigators()

    # statistics for investigator
    inv_mean_cost = all_decks[all_decks['investigator_name']==investigator['name'][0]]['mean_cost'].mean()

    inv_assets_percentage = all_decks[all_decks['investigator_name']==investigator['name'][0]]['asset_percentages'].mean()
    inv_events_percentage = all_decks[all_decks['investigator_name']==investigator['name'][0]]['event_percentages'].mean()
    inv_skills_percentage = all_decks[all_decks['investigator_name']==investigator['name'][0]]['skill_percentages'].mean()

    inv_hand_slot = all_decks[all_decks['investigator_name']==investigator['name'][0]]['hand_slot'].mean()
    inv_arcane_slot = all_decks[all_decks['investigator_name']==investigator['name'][0]]['arcane_slot'].mean()
    inv_ally_slot = all_decks[all_decks['investigator_name']==investigator['name'][0]]['ally_slot'].mean()
    inv_body_slot = all_decks[all_decks['investigator_name']==investigator['name'][0]]['body_slot'].mean()
    inv_accessory_slot = all_decks[all_decks['investigator_name']==investigator['name'][0]]['accessory_slot'].mean()

    inv_skill_willpower = all_decks[all_decks['investigator_name']==investigator['name'][0]]['skill_willpower'].mean()
    inv_skill_combat = all_decks[all_decks['investigator_name']==investigator['name'][0]]['skill_combat'].mean()
    inv_skill_agility = all_decks[all_decks['investigator_name']==investigator['name'][0]]['skill_agility'].mean()
    inv_skill_intellect = all_decks[all_decks['investigator_name']==investigator['name'][0]]['skill_intellect'].mean()
    inv_skill_wild = all_decks[all_decks['investigator_name']==investigator['name'][0]]['skill_wild'].mean()

    # average statistics for all others
    others_mean_cost = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['mean_cost'].mean()

    others_assets_percentage = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['asset_percentages'].mean()
    others_events_percentage = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['event_percentages'].mean()
    others_skills_percentage = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['skill_percentages'].mean()

    others_hand_slot = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['hand_slot'].mean()
    others_arcane_slot = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['arcane_slot'].mean()
    others_ally_slot = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['ally_slot'].mean()
    others_body_slot = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['body_slot'].mean()
    others_accessory_slot = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['accessory_slot'].mean()

    others_skill_willpower = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['skill_willpower'].mean()
    others_skill_combat = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['skill_combat'].mean()
    others_skill_agility = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['skill_agility'].mean()
    others_skill_intellect = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['skill_intellect'].mean()
    others_skill_wild = all_decks[all_decks['investigator_name']!=investigator['name'][0]]['skill_wild'].mean()
   
    # average statistics for investigator's faction

    all_decks = all_decks.join(investigators[['name','faction_code']].set_index('name'), on='investigator_name', rsuffix="r_")

    faction_mean_cost = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['mean_cost'].mean()
    
    faction_assets_percentage = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['asset_percentages'].mean()
    faction_events_percentage = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['event_percentages'].mean()
    faction_skills_percentage = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['skill_percentages'].mean()

    faction_hand_slot = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['hand_slot'].mean()
    faction_arcane_slot = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['arcane_slot'].mean()
    faction_ally_slot = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['ally_slot'].mean()
    faction_body_slot = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['body_slot'].mean()
    faction_accessory_slot = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['accessory_slot'].mean()

    faction_skill_willpower = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['skill_willpower'].mean()
    faction_skill_combat = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['skill_combat'].mean()
    faction_skill_agility = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['skill_agility'].mean()
    faction_skill_intellect = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['skill_intellect'].mean()
    faction_skill_wild = all_decks[(all_decks['investigator_name']!=investigator['name'][0]) & (all_decks['faction_code']==investigator['faction_code'][0])]['skill_wild'].mean()

    deck_statistics = {
        'others_mean_cost': others_mean_cost,
        'others_assets_percentage': others_assets_percentage*100,
        'others_skills_percentage': others_skills_percentage*100,
        'others_events_percentage': others_events_percentage*100,
        'others_hand_slot': others_hand_slot,
        'others_arcane_slot': others_arcane_slot,
        'others_body_slot': others_body_slot,
        'others_accessory_slot': others_accessory_slot,
        'others_ally_slot': others_ally_slot,
        'others_skill_willpower': others_skill_willpower,
        'others_skill_agility': others_skill_agility,
        'others_skill_combat': others_skill_combat,
        'others_skill_intellect': others_skill_intellect,
        'others_skill_wild': others_skill_wild,
        'inv_mean_cost': inv_mean_cost,
        'inv_assets_percentage': inv_assets_percentage*100,
        'inv_events_percentage': inv_events_percentage*100,
        'inv_skills_percentage': inv_skills_percentage*100,
        'inv_hand_slot': inv_hand_slot,
        'inv_arcane_slot': inv_arcane_slot,
        'inv_body_slot': inv_body_slot,
        'inv_accessory_slot': inv_accessory_slot,
        'inv_ally_slot': inv_ally_slot,
        'inv_skill_willpower': inv_skill_willpower,
        'inv_skill_agility': inv_skill_agility,
        'inv_skill_combat': inv_skill_combat,
        'inv_skill_intellect': inv_skill_intellect,
        'inv_skill_wild': inv_skill_wild,
        'faction_mean_cost': faction_mean_cost,
        'faction_assets_percentage': faction_assets_percentage*100,
        'faction_skills_percentage': faction_skills_percentage*100,
        'faction_events_percentage': faction_events_percentage*100,
        'faction_hand_slot': faction_hand_slot,
        'faction_arcane_slot': faction_arcane_slot,
        'faction_body_slot': faction_body_slot,
        'faction_accessory_slot': faction_accessory_slot,
        'faction_ally_slot': faction_ally_slot,
        'faction_skill_willpower': faction_skill_willpower,
        'faction_skill_agility': faction_skill_agility,
        'faction_skill_combat': faction_skill_combat,
        'faction_skill_intellect': faction_skill_intellect,
        'faction_skill_wild': faction_skill_wild,
        }

    return deck_statistics
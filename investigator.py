import code
from dataclasses import asdict
from distutils.log import info
from lib2to3.pytree import convert
from sqlite3 import adapters
from unicodedata import name
from flask import current_app
import os

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('investigator', __name__, url_prefix='/investigator')

@bp.route('/', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        
        return redirect(url_for('investigator.view', investigator_id=request.form['investigator_id']))

    import pandas as pd

    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    # card_frequencies_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))
    # card_cooc = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cooc.pickle'))
    all_decks_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))

    num_of_decks = len(all_decks_clean)

    all_investigators = card_cycles[card_cycles['type_code']=="investigator"]
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'])
    investigator_unique_codes = all_investigators.groupby('name')['code'].min()
    card_cycles.loc[:,'code'] = pd.to_numeric(card_cycles['code'], errors='coerce')
    investigators = card_cycles[card_cycles['code'].isin(investigator_unique_codes.values)].set_index('name')

    number_of_decks_per_investigator = all_decks_clean.groupby('investigator_name').count()['id'].to_frame()
    number_of_decks_per_investigator.columns = ['number_of_decks']
    investigators = investigators.join(number_of_decks_per_investigator)

    
    
    
    investigators['color'] = investigators['faction_code']
    investigators.loc[investigators['faction2_code'].notna(),'color']='multi'
    investigators = investigators.fillna("-")
    print(investigators)
    investigators = investigators[investigators['number_of_decks']!='-']
    print(investigators)
    investigators = investigators.reset_index().set_index('code_str')
    print(investigators)
    
    return render_template('investigator/search.html', investigators=investigators.to_dict(orient='index'),num_of_decks=num_of_decks)

@bp.route('/<investigator_id>', methods=['GET'])
def view(investigator_id):
    import pandas as pd

    #################################################################
    # Reads files
    #################################################################

    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    all_decks_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle')) 
    inv_cooc_ratio = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'inv_cooc_ratio.pickle'))
    card_frequencies_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))   
    card_cooc = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cooc.pickle'))

    #################################################################
    # Builds list of all investigators from card pool
    #################################################################

    all_investigators = card_cycles[card_cycles['type_code']=="investigator"]
    
    # There are investigators with multiple codes (e.g. parallel versions, book versions, etc.)
    # Gets the minimum code (that's the "cycle" version)
    # Converts to numeric to find the minimum value
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'])
    investigator_unique_codes = all_investigators.groupby('name')['code'].min() 
    card_cycles.loc[:,'code'] = pd.to_numeric(card_cycles['code'], errors='coerce')
    investigators = card_cycles[card_cycles['code'].isin(investigator_unique_codes.values)].set_index('name')

    ##################################################################
    # Populate investigator list with deck metrics
    ##################################################################

    # total number of decks in database
    number_of_decks_per_investigator = all_decks_clean.groupby('investigator_name').count()['id'].to_frame()
    number_of_decks_per_investigator.columns = ['number_of_decks']
    investigators = investigators.join(number_of_decks_per_investigator)
    # gets rank between all investigators
    investigators['occurrences_rank'] = investigators['number_of_decks'].rank(method="max", ascending=False)
    # creates string for faction color - really useless since there is no "multi" colored investigator
    investigators['color'] = investigators['faction_code']
    investigators.loc[investigators['faction2_code'].notna(),'color']='multi'
    investigators = investigators.fillna("-")
    # removes investigators with no decks (currently, only the ones from the TCU prologue)
    investigators = investigators[investigators['number_of_decks']!='-']
    investigators = investigators.reset_index().set_index('code_str')

    ###################################################################
    # Gets the selected investigator from investigators list
    ###################################################################
    investigator = investigators.loc[investigator_id].to_frame()
    investigator = investigator.transpose()

    ###################################################################
    # Gets total number of decks and investigators (for the view)
    ###################################################################

    num_of_decks = len(all_decks_clean)
    num_of_investigators = len(investigators)    
    

    ####################################################################
    # Prepares the cards database for the view
    ####################################################################

    card_cycles_clean = card_cycles.set_index('code_str')

    # Keeps only the cards that have cooccurrences calculates
    card_cycles_clean = card_cycles_clean.merge(card_frequencies_clean, left_index=True, right_index=True)

    # Joins the number of cooccurrences of each card with this investigator
    inv_card_cooccurrences = inv_cooc_ratio.loc[investigator['name'][0]].transpose().to_frame('inv_occurrence')
    card_cycles_clean = card_cycles_clean.join(inv_card_cooccurrences)


    # Joins the number of occurrences of each card
    # Uses pandas multiindex to facilitate retrieving the data
    # This basically transforms a 2x2 matrix in a "database" style
    tuples = list(zip(card_cooc.index, card_cooc.index))
    card_cooc_stacked = card_cooc.stack()[tuples].to_frame('Occurrences').reset_index(level=[0])
    card_cycles_clean = card_cycles_clean.join(card_cooc_stacked)

    # Cleans the XP value for visualization    
    card_cycles_clean.loc[:,'xp_text'] = card_cycles_clean['xp']
    card_cycles_clean = convert_xp_to_str(card_cycles_clean)

    # Creates string with the color of the card (useful for multicolored ones)
    card_cycles_clean['color'] = card_cycles_clean['faction_code']
    card_cycles_clean.loc[card_cycles_clean['faction2_code'].notna(),'color']='multi'
    
    # Calculates the synergy with investigator
    card_cycles_clean['overall_occurrence_ratio'] = card_cycles_clean['Occurrences'] / num_of_decks
    card_cycles_clean['synergy'] = card_cycles_clean['inv_occurrence'] - card_cycles_clean['overall_occurrence_ratio']

    # Ranks the card
    card_cycles_clean['occurrences_rank'] = card_cycles_clean['Occurrences'].rank(method="max", ascending=False)
    
    card_cycles_clean = card_cycles_clean.fillna("-")

    ####################################################################
    # Calculates deck statistics
    ####################################################################

    # statistics for investigator
    inv_mean_cost = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['mean_cost'].mean()

    inv_assets_percentage = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['asset_percentages'].mean()
    inv_events_percentage = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['event_percentages'].mean()
    inv_skills_percentage = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['skill_percentages'].mean()

    inv_hand_slot = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['hand_slot'].mean()
    inv_arcane_slot = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['arcane_slot'].mean()
    inv_ally_slot = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['ally_slot'].mean()
    inv_body_slot = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['body_slot'].mean()
    inv_accessory_slot = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['accessory_slot'].mean()

    inv_skill_willpower = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['skill_willpower'].mean()
    inv_skill_combat = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['skill_combat'].mean()
    inv_skill_agility = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['skill_agility'].mean()
    inv_skill_intellect = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['skill_intellect'].mean()
    inv_skill_wild = all_decks_clean[all_decks_clean['investigator_name']==investigator['name'][0]]['skill_wild'].mean()

    # average statistics for all others
    others_mean_cost = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['mean_cost'].mean()

    others_assets_percentage = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['asset_percentages'].mean()
    others_events_percentage = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['event_percentages'].mean()
    others_skills_percentage = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['skill_percentages'].mean()

    others_hand_slot = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['hand_slot'].mean()
    others_arcane_slot = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['arcane_slot'].mean()
    others_ally_slot = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['ally_slot'].mean()
    others_body_slot = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['body_slot'].mean()
    others_accessory_slot = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['accessory_slot'].mean()

    others_skill_willpower = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['skill_willpower'].mean()
    others_skill_combat = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['skill_combat'].mean()
    others_skill_agility = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['skill_agility'].mean()
    others_skill_intellect = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['skill_intellect'].mean()
    others_skill_wild = all_decks_clean[all_decks_clean['investigator_name']!=investigator['name'][0]]['skill_wild'].mean()
   
    

    # average statistics for investigator's faction

    all_decks_clean = all_decks_clean.join(investigators[['name','faction_code']].set_index('name'), on='investigator_name', rsuffix="r_")

    faction_mean_cost = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['mean_cost'].mean()
    
    faction_assets_percentage = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['asset_percentages'].mean()
    faction_events_percentage = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['event_percentages'].mean()
    faction_skills_percentage = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['skill_percentages'].mean()

    faction_hand_slot = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['hand_slot'].mean()
    faction_arcane_slot = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['arcane_slot'].mean()
    faction_ally_slot = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['ally_slot'].mean()
    faction_body_slot = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['body_slot'].mean()
    faction_accessory_slot = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['accessory_slot'].mean()

    faction_skill_willpower = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['skill_willpower'].mean()
    faction_skill_combat = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['skill_combat'].mean()
    faction_skill_agility = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['skill_agility'].mean()
    faction_skill_intellect = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['skill_intellect'].mean()
    faction_skill_wild = all_decks_clean[(all_decks_clean['investigator_name']!=investigator['name'][0]) & (all_decks_clean['faction_code']==investigator['faction_code'][0])]['skill_wild'].mean()

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

    ####################################################################
    # Calculates average deck
    ####################################################################

    deck_reqs = investigator['deck_requirements'][0].split(',')
    
    card_reqs_codes = ['01000']
    for req in deck_reqs:
        req_tuple = req.split(':',1)
        if(req_tuple[0]=='size'):
            deck_size = int(req_tuple[1])
        elif (req_tuple[0].strip()=='card'):
            card_reqs_codes.append(req_tuple[1].split(':')[0])
                
       
    card_reqs = card_cycles[card_cycles['code_str'].isin(card_reqs_codes)]
    card_reqs_quants = card_reqs.groupby('type_code')['quantity'].sum()

    total_deck_size = deck_size + card_reqs_quants.sum()

    # print(card_reqs_quants)

    # print(card_reqs_quants['skills'] if 'skill' in card_reqs_quants.index else 0)
    print((total_deck_size * inv_assets_percentage))
    print((total_deck_size * inv_events_percentage))
    
    assets_to_include = round((total_deck_size * inv_assets_percentage) - (card_reqs_quants['asset'] if 'asset' in card_reqs_quants.index else 0))
    if(assets_to_include % 2 == 1):
        assets_to_include+=1
    events_to_include = round((total_deck_size * inv_events_percentage) - (card_reqs_quants['event'] if 'event' in card_reqs_quants.index else 0))
    if(events_to_include % 2 == 1):
        events_to_include+=1
    skills_to_include = deck_size - assets_to_include - events_to_include
    print("\n\n\n")
    print("Assets to include: {:d}".format(assets_to_include))
    print("Events to include: {:d}".format(events_to_include))
    print("Skills to include: {:d}".format(skills_to_include))
    print("\n\n\n")
    card_cycles_pool = card_cycles_clean.drop(card_reqs.set_index('code_str').index, errors='ignore')

    assets = card_cycles_pool[card_cycles_pool['type_code']=='asset'].sort_values('inv_occurrence', ascending=False).head(int(assets_to_include / 2))
    events = card_cycles_pool[card_cycles_pool['type_code']=='event'].sort_values('inv_occurrence', ascending=False).head(int(events_to_include / 2))
    skills = card_cycles_pool[card_cycles_pool['type_code']=='skill'].sort_values('inv_occurrence', ascending=False).head(int(skills_to_include / 2))

    average_deck = skills.append(assets.append(events))


    return render_template('investigator/view.html', investigator_info=investigator.to_dict(orient='index'), investigator_id=investigator_id, card_info=card_cycles_clean.to_dict(orient='index'), num_of_decks=num_of_decks, num_of_investigators=num_of_investigators, deck_statistics=deck_statistics, average_deck = average_deck.to_dict(orient='index'))

def convert_xp_to_str(cards):
    cards.loc[:,'xp'] = cards.loc[:,'xp'].to_frame().applymap(lambda x: "{:0.0f}".format(x) if x>0 else '')
    return cards
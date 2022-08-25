from dataclasses import asdict
from flask import current_app
import os
import arkhrec.helpers
import math

from flask import (
    Blueprint, redirect, render_template, request, url_for
)

bonus_experience = {
    'Father Mateo': 5
}

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
    investigators = investigators[investigators['number_of_decks']!='-']
    investigators = investigators.reset_index().set_index('code_str')
      
    return render_template('investigator/search.html', investigators=investigators.to_dict(orient='index'),num_of_decks=num_of_decks)

@bp.route('/<investigator_id>', methods=['GET'])
def view(investigator_id):
    import pandas as pd

    card_collection = arkhrec.helpers.get_collection()

    #################################################################
    # Reads files
    #################################################################

    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))
    card_cycles.loc[:,'unique_code'] = card_cycles.loc[:, 'code_str']
    card_cycles.loc[~card_cycles['duplicate_of'].isna(), 'unique_code'] = card_cycles.loc[~card_cycles['duplicate_of'].isna(), 'duplicate_of'].astype(int).astype(str).apply(str.zfill, args=[5])
    card_collection_codes = card_cycles[card_cycles['pack_code'].isin(card_collection.keys())]['unique_code'].unique()

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
    investigator['text_icons'] = arkhrec.helpers.convert_text_to_icons(investigator['text'][0])

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


    import collections

    deck_size_selected = collections.Counter()
    faction_selected = collections.Counter()
    two_factions_selected = collections.Counter()
    alternate_front = collections.Counter()
    alternate_back = collections.Counter()
    option_selected = collections.Counter()

    choice_decks=all_decks_clean[all_decks_clean['investigator_name'] == investigator['name'][0]]

    import ast

    for m in choice_decks.meta:
        if m:
            m = ast.literal_eval(m)
            if 'deck_size_selected' in m:
                deck_size_selected[m['deck_size_selected']] = deck_size_selected[m['deck_size_selected']] + 1/len(choice_decks.meta)
            if 'faction_selected' in m:
                faction_selected[m['faction_selected']] = faction_selected[m['faction_selected']] + 1/len(choice_decks.meta)
            if 'option_selected' in m:
                option_selected[m['option_selected']] = option_selected[m['option_selected']] + 1/len(choice_decks.meta)
            if 'alternate_front' in m:
                alternate_front[m['alternate_front']] = alternate_front[m['alternate_front']] + 1/len(choice_decks.meta)
            if 'alternate_back' in m:
                alternate_back[m['alternate_back']] = alternate_back[m['alternate_back']] + 1/len(choice_decks.meta)
            if 'faction_1' in m:
                two_factions_selected[m['faction_1']] = two_factions_selected[m['faction_1']] + 1/len(choice_decks.meta)
            if 'faction_2' in m:
                two_factions_selected[m['faction_2']] = two_factions_selected[m['faction_2']] + 1/len(choice_decks.meta)

    deck_size_selected['none'] = 1-sum(deck_size_selected.values())
    two_factions_selected['none']=2-sum(two_factions_selected.values())
    faction_selected['none'] = 1-sum(faction_selected.values())
    option_selected['none'] = 1-sum(option_selected.values())
    alternate_front['none'] = 1-sum(alternate_front.values())
    alternate_back['none'] = 1-sum(alternate_back.values())

    max_faction_selected = max(faction_selected, key=faction_selected.get)
    max_deck_size_selected = max(deck_size_selected, key=deck_size_selected.get)
    
    df_two_factions_selected = pd.DataFrame.from_dict(two_factions_selected, orient='index')
    df_two_factions_selected.columns = ['percentage']
    max_two_factions = df_two_factions_selected['percentage'].nlargest(2)
    max_faction_1 = df_two_factions_selected[df_two_factions_selected['percentage'] == max_two_factions[0]].head().index[0]
    max_faction_2 = df_two_factions_selected[df_two_factions_selected['percentage'] == max_two_factions[len(max_two_factions)-1]].head().index[0]


    inv_card_deck = card_cycles.set_index('code_str').loc[investigator_id]

    if(max_deck_size_selected != 'none'):
        deck_size = int(max_deck_size_selected)

    total_deck_size = deck_size + card_reqs_quants.sum()
    
    assets_to_include = round((total_deck_size * inv_assets_percentage) - (card_reqs_quants['asset'] if 'asset' in card_reqs_quants.index else 0))
    if(assets_to_include % 2 == 1):
        assets_to_include+=1
    events_to_include = round((total_deck_size * inv_events_percentage) - (card_reqs_quants['event'] if 'event' in card_reqs_quants.index else 0))
    if(events_to_include % 2 == 1):
        events_to_include+=1
    skills_to_include = deck_size - assets_to_include - events_to_include

    card_cycles_pool = card_cycles_clean.drop(card_reqs.set_index('code_str').index, errors='ignore')
    card_cycles_pool = card_cycles_pool.loc[card_cycles_pool.index.intersection(card_collection_codes)]
    card_cycles_pool.loc[:,'xp'] = pd.to_numeric(card_cycles_pool['xp'], errors='coerce')
  
    card_pool = cards_valid_for_investigator(card_cycles_pool, inv_card_deck.deck_options, max_faction_selected, [max_faction_1, max_faction_2])
        
    card_pool = card_pool.sort_values(['inv_occurrence','synergy'],ascending=False)
    card_pool_xp = card_pool[card_pool['xp']>0]
    card_pool = card_pool[card_pool['xp']==0]
    exclusion_cards = ['In the Thick of It', 'Underworld Support']
    card_pool = card_pool[~(card_pool['name'].isin(exclusion_cards))]
    

    assets_card_pool = card_pool[card_pool['type_code']=='asset']
    assets_card_pool.loc[:, 'cumsum_deck_limit'] = assets_card_pool['deck_limit'].cumsum()

    events_card_pool = card_pool[card_pool['type_code']=='event']
    events_card_pool.loc[:, 'cumsum_deck_limit'] = events_card_pool['deck_limit'].cumsum()

    skills_card_pool = card_pool[card_pool['type_code']=='skill']
    skills_card_pool.loc[:, 'cumsum_deck_limit'] = skills_card_pool['deck_limit'].cumsum()


    # assets = card_pool[card_pool['type_code']=='asset'].sort_values('inv_occurrence', ascending=False).head(int(assets_to_include / 2))
    assets = assets_card_pool[assets_card_pool['cumsum_deck_limit']<=assets_to_include]
    events = events_card_pool[events_card_pool['cumsum_deck_limit']<=events_to_include]
    skills = skills_card_pool[skills_card_pool['cumsum_deck_limit']<=skills_to_include]

    average_deck = skills.append(assets.append(events))
    average_deck.loc[:,'amount'] = average_deck['deck_limit']

    # check deck size
    final_deck_size = average_deck['amount'].sum()

    while final_deck_size < deck_size:
        new_card_pool = card_pool.drop(average_deck.index, errors='ignore').sort_values(['inv_occurrence','synergy'], ascending=False)
        if new_card_pool.empty:
            break
        
        new_card_pool.loc[:,'cumsum_deck_limit'] = new_card_pool['deck_limit'].cumsum()
        next_card_to_include = new_card_pool.head(1)

        
        if (final_deck_size - deck_size) < next_card_to_include['deck_limit'][0]:

            next_card_to_include['amount'] =  deck_size - final_deck_size
            inclusions_to_deck = next_card_to_include

        else:

            inclusions_to_deck = new_card_pool[new_card_pool['cumsum_deck_limit']<(final_deck_size - deck_size)]
            inclusions_to_deck.loc[:,'amount'] = inclusions_to_deck['deck_limit']

            
            
        
        average_deck = average_deck.append(inclusions_to_deck)  

        
        final_deck_size = average_deck['amount'].sum()

    if investigator['name'][0] in bonus_experience:
        xp_cards_to_include = pd.DataFrame()
        total_xp_to_include = bonus_experience[investigator['name'][0]]
        xp_to_include = total_xp_to_include
        # Get xp cards to include
        while True:
            if card_pool_xp.empty:
                break
            card_pool_xp.loc[:, 'cumsum_deck_limit'] = card_pool_xp['deck_limit'].cumsum()
            card_pool_xp.loc[:, 'total_xp'] = card_pool_xp['deck_limit'] * card_pool_xp['xp']
            card_pool_xp.loc[card_pool_xp['myriad']==1, 'total_xp'] = card_pool_xp.loc[card_pool_xp['myriad']==1,'xp']
            card_pool_xp.loc[:, 'cumsum_xp'] = card_pool_xp['total_xp'].cumsum()
            if card_pool_xp.head(1)['xp'][0] > xp_to_include:
                card_pool_xp = card_pool_xp.drop(card_pool_xp.head(1).index)
            elif card_pool_xp.head(1)['cumsum_xp'][0] > xp_to_include:
                xp_cards = card_pool_xp.head(1)
                card_pool_xp = card_pool_xp.drop(xp_cards.index)
                xp_cards.loc[:,'amount'] = math.floor(xp_to_include / xp_cards['xp'])
                xp_cards_to_include = xp_cards_to_include.append(xp_cards)
            else:
                
                xp_cards = card_pool_xp[card_pool_xp['cumsum_xp']<xp_to_include]
                
                card_pool_xp = card_pool_xp.drop(xp_cards.index)
                xp_cards.loc[:,'amount'] = xp_cards['deck_limit']
                xp_cards_to_include = xp_cards_to_include.append(xp_cards)
                
            
            xp_cards_to_include.loc[:,'total_xp'] = xp_cards_to_include['amount'] * xp_cards_to_include['xp']
            included_xp = xp_cards_to_include['total_xp'].sum()
            xp_to_include = total_xp_to_include - included_xp
            if xp_to_include <= 0:
                break
        if not xp_cards_to_include.empty:
            # Exclude least similar 0xp cards
            number_of_cards_to_include = xp_cards_to_include['amount'].sum()
            average_deck = average_deck.sort_values('inv_occurrence')
            average_deck.loc[:,"cumsum_amount"] = average_deck['amount'].cumsum()
            
            number_of_cards_to_exclude = number_of_cards_to_include
            while True:
                if average_deck.head(1)['cumsum_amount'][0] > number_of_cards_to_exclude:
                    
                    
                    average_deck.at[average_deck.head(1).index[0], 'amount'] = average_deck.head(1)['amount']-number_of_cards_to_exclude
                    
                    
                else:
                    
                    average_deck = average_deck[average_deck['cumsum_amount']>number_of_cards_to_exclude]
                    
                number_of_cards_to_exclude = average_deck['amount'].sum()+number_of_cards_to_include-deck_size
                
                if average_deck['amount'].sum() <= deck_size - number_of_cards_to_include:
                    break
            average_deck = average_deck.append(xp_cards_to_include)




    average_deck.sort_values(['type_code','inv_occurrence'])
    average_deck['color'] = average_deck['faction_code']
    average_deck['total_xp'] = average_deck['amount'] * average_deck['xp']
    
    average_deck.loc[average_deck['faction2_code']!="-",'color']='multi'
    average_deck = average_deck.sort_values('type_code')

    print("\n\n\n\n\nAVERAGE DECK")
    print(average_deck)

    card_cycles_clean['cycle'] = card_cycles_clean.apply(arkhrec.helpers.set_cycle, axis=1)
    print(card_reqs.set_index('code_str'))
    card_cycles_clean = card_cycles_clean.drop(card_reqs['code_str'], errors='ignore')
    card_cycles_clean = card_cycles_clean.loc[card_cycles_clean.index.intersection(card_collection_codes)]
    
    return render_template('investigator/view.html', investigator_info=investigator.to_dict(orient='index'), investigator_id=investigator_id, card_info=card_cycles_clean.to_dict(orient='index'), num_of_decks=num_of_decks, num_of_investigators=num_of_investigators, deck_statistics=deck_statistics, average_deck = average_deck.to_dict(orient='index'), average_deck_size = average_deck['amount'].sum(), average_deck_xp = average_deck['total_xp'].sum())

def convert_xp_to_str(cards):
    cards.loc[:,'xp_text'] = cards.loc[:,'xp_text'].to_frame().applymap(lambda x: "{:0.0f}".format(x) if x>0 else '')
    return cards

def cards_valid_for_investigator(card_cycles_pool, deck_options, single_faction_selected='', multi_faction_selected=[]):
    import pandas as pd

    card_pools=[]
    for do in deck_options:
        if 'faction' in do and 'level' in do and 'limit' not in do:
                restriction_pool = card_cycles_pool[(card_cycles_pool['faction_code'].isin(do['faction'])) & (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1)))]
                card_pools.append(restriction_pool)
                # Dunwich splash
                main_factions = do['faction']
        elif 'faction' in do and 'level' in do and 'limit' in do:
            restriction_pool = card_cycles_pool[(card_cycles_pool['faction_code'].isin(do['faction'])) & card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1))].sort_values('inv_occurrence', ascending=False).head(do['limit'])
            # filter_limits.append({'factions': do['faction'], 'level': do['level'], 'limit': do['limit']})
        elif 'level' in do and 'faction' not in do and 'limit' in do:
            factions = ['guardian', 'mystic', 'seeker', 'rogue', 'survivor', 'neutral']
            filter_classes = factions
            
            for f in main_factions:
                filter_classes.remove(f)
            
            
            restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'].isin(filter_classes)) | (card_cycles_pool['faction2_code'].isin(filter_classes)) | (card_cycles_pool['faction3_code'].isin(filter_classes)) ) & card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1))].sort_values('inv_occurrence', ascending=False).head(do['limit'])
            
            # filter_limits.append({'factions': filter_classes, 'level': do['level'], 'limit': do['limit']})  
        elif 'name' in do:
            if do['name'] == 'Secondary Class':
                restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'] == single_faction_selected)| (card_cycles_pool['faction2_code'] == single_faction_selected) | (card_cycles_pool['faction3_code'] == single_faction_selected) ) & (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1))) & (card_cycles_pool['type_code'].isin(do['type']))]
                if 'limit' in do and 'type' in do:
                    restriction_pool = restriction_pool[restriction_pool["type_code"]==do['type']].sort_values('inv_occurrence', ascending=False).head(do['limit'])
                    # filter_limits.append({'factions': do['faction'], 'level': do['level'], 'type': do['type'], 'limit': do['limit']})
                elif 'limit' in do and 'type' not in do:
                    restriction_pool = restriction_pool.sort_values('inv_occurrence', ascending=False).head()
                    # filter_limits.append({'factions': do['faction'], 'level': do['level'], 'limit': do['limit']})
                card_pools.append(restriction_pool)
            elif do['name'] == "Class Choice":
                if do['id'] == 'faction_1':
                    restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'] == multi_faction_selected[0]) | (card_cycles_pool['faction2_code'] == multi_faction_selected[0]) | (card_cycles_pool['faction3_code'] == multi_faction_selected[0]) ) & (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1)))]

                    card_pools.append(restriction_pool)
                elif do['id'] == 'faction_2':
                    
                    restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'] == multi_faction_selected[1]) | (card_cycles_pool['faction2_code'] == multi_faction_selected[1]) | (card_cycles_pool['faction3_code'] == multi_faction_selected[1]) )& (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1)))]
                    card_pools.append(restriction_pool)


    card_pool = pd.concat(card_pools)

    card_pool = card_pool.loc[card_pool.astype(str).drop_duplicates().index]
    card_pool.loc[:,'deck_limit'] = pd.to_numeric(card_pool['deck_limit'], errors='coerce')
    
    return card_pool



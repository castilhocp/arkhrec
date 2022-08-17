import functools
from flask import current_app
import os

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('deck', __name__, url_prefix='/deck')

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
    

    card_cycles = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_cycles.pickle'))

    duplicates = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'duplicates.pickle'))
    card_jaccard_score = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_jaccard_score.pickle'))
    
    inv_cooc_ratio = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'inv_cooc_ratio.pickle'))
    all_decks_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'all_decks_clean.pickle'))
    card_frequencies_clean = pd.read_pickle(os.path.join(current_app.root_path, 'datafiles',  'card_frequencies_clean.pickle'))

    # Remove duplicate cards and substitute code for the "principal" copy
    duplicates_in_deck = duplicates.loc[list((set(deck_to_compare['slots'][0].keys()) & set(duplicates.index)))]
    deck_to_compare.loc[:,'slots'][0] = {duplicates_in_deck.loc[k]['duplicate_of_str'] if k in duplicates_in_deck.index else k:v for k,v in deck_to_compare['slots'][0].items()}
    deck_to_compare_clean = deck_to_compare.copy()
    deck_to_compare_clean.loc[:,'slots'][0] = {card: value for (card,value) in deck_to_compare['slots'][0].items() if card in card_frequencies_clean.index}
    # Fetch the jaccard scores for the cards in the deck
    deck_jaccards = card_jaccard_score[deck_to_compare_clean['slots'][0].keys()]
    # Sum the jaccard scores for each card of the deck
    recommendations = deck_jaccards.sum(axis=1).sort_values(ascending=False)
    # See possible inclusions (drops cards already in deck)
    inclusion_recs = recommendations.drop(deck_to_compare_clean['slots'][0].keys()).to_frame('Jaccard Score')
    inclusion_recs.loc[:,'Jaccard Score'] = inclusion_recs.applymap(lambda x: "{:0.2f}".format(x))
    inclusion_recs = inclusion_recs.join(card_cycles[['code_str','name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code','xp']].set_index('code_str'))
    
    inclusion_recs = inclusion_recs[inclusion_recs['type_code'].isin(['asset','event', 'skill'])][['name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp', 'Jaccard Score']]
    
    exclusion_recs = recommendations[deck_to_compare_clean['slots'][0].keys()].to_frame('Jaccard Score')
    exclusion_recs.loc[:,'Jaccard Score'] = exclusion_recs.applymap(lambda x: "{:0.2f}".format(x))
    # exclusion_recs_template = exclusion_recs.join(card_cycles[['code_str','name','pack_code', 'faction_code']].set_index('code_str')).sort_values(by='Jaccard Score').to_dict('index')
    inv_recommendations = inv_cooc_ratio.loc[deck_to_compare['investigator_name'][0],:].transpose().to_frame('Coocurrence')
    inv_recommendations.loc[:,'Coocurrence'] = inv_recommendations.applymap(lambda x: "{:0.0%}".format(x))
    inv_inclusion_recs = inv_recommendations[~inv_recommendations.index.isin(deck_to_compare['slots'][0].keys())].join(card_cycles[['code_str','name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp']].set_index('code_str'))

    inclusion_recs = inclusion_recs.join(inv_inclusion_recs['Coocurrence'])

    # inv_inclusion_recs = inv_inclusion_recs[inv_inclusion_recs['type_code'].isin(['asset','event', 'skill'])][['name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp', 'Coocurrence']]
    # inv_inclusion_recs = inv_inclusion_recs.sort_values(by=inv_recommendations.columns[0],ascending=False)
    
    # print(inv_inclusion_recs)
    inv_exclusion_recs = inv_recommendations[inv_recommendations.index.isin(deck_to_compare['slots'][0].keys())].join(card_cycles[['code_str','name','pack_code', 'faction_code']].set_index('code_str')).sort_values(by=inv_recommendations.columns[0],ascending=True)

    # deck_to_compare_with_info = pd.DataFrame.from_dict(deck_to_compare['slots'][0],orient='index').join(card_cycles[['code_str','name','type_code','cost']].set_index('code_str'))
    deck_to_compare_with_info = pd.DataFrame.from_dict(deck_to_compare['slots'][0],orient='index').join(
            card_cycles[['code_str','name','type_code','cost',"skill_willpower", "skill_agility", "skill_combat", "skill_intellect", "skill_wild", "slot"]].set_index(
            'code_str'))

    deck_to_compare_with_info.loc[:,['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']]=deck_to_compare_with_info[['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']].multiply(deck_to_compare_with_info[0],axis='index')
    pips_sum = deck_to_compare_with_info[['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']].sum()
    slots_count = deck_to_compare_with_info.groupby('slot')[0].sum()
    

    type_distribution = deck_to_compare_with_info.groupby('type_code')[0].sum()
    type_distribution = type_distribution / type_distribution.sum()
    #type_distribution

    deck_to_compare_with_info['w_costs']=deck_to_compare_with_info['cost'] * deck_to_compare_with_info[0]
    mean_cost = deck_to_compare_with_info[~deck_to_compare_with_info.cost.isnull()]['w_costs'].sum() / deck_to_compare_with_info[~deck_to_compare_with_info.cost.isnull()][0].sum()
    assets_percentage = type_distribution['asset'] if 'asset' in type_distribution.index else 0
    skills_percentage = type_distribution['skill'] if 'skill' in type_distribution.index else 0
    events_percentage = type_distribution['event'] if 'event' in type_distribution.index else 0
    
    skill_willpower = pips_sum['skill_willpower'] if 'skill_willpower' in pips_sum.index else 0
    skill_combat = pips_sum['skill_combat'] if 'skill_combat' in pips_sum.index else 0
    skill_intellect = pips_sum['skill_intellect'] if 'skill_intellect' in pips_sum.index else 0
    skill_agility = pips_sum['skill_agility'] if 'skill_agility' in pips_sum.index else 0
    skill_wild = pips_sum['skill_wild'] if 'skill_wild' in pips_sum.index else 0
    slots_count = slots_count.index * slots_count
    slots_count = slots_count.str.cat().replace("Hand x2", "HandHand").replace("Arcane x2", "ArcaneArcane").replace("Accessory x2", "AccessoryAccessory").replace("Body x2", "BodyBody").replace("Ally x2", "AllyAlly")
    hand_slot = slots_count.count("Hand")
    arcane_slot = slots_count.count("Arcane")
    accessory_slot = slots_count.count("Accessory")
    body_slot = slots_count.count("Body")
    ally_slot = slots_count.count("Ally")

    # treachery_percentage = type_distribution['treachery'] if 'treachery' in type_distribution.index else 0
    inv_mean_cost = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['mean_cost'].mean()
    inv_assets_percentage = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['asset_percentages'].mean()
    inv_events_percentage = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['event_percentages'].mean()
    inv_skills_percentage = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_percentages'].mean()

    inv_hand_slot = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['hand_slot'].mean()
    inv_arcane_slot = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['arcane_slot'].mean()
    inv_ally_slot = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['ally_slot'].mean()
    inv_body_slot = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['body_slot'].mean()
    inv_accessory_slot = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['accessory_slot'].mean()

    inv_skill_willpower = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_willpower'].mean()
    inv_skill_combat = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_combat'].mean()
    inv_skill_agility = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_agility'].mean()
    inv_skill_intellect = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_intellect'].mean()
    inv_skill_wild = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_wild'].mean()

    deck_statistics = {
        'mean_cost': mean_cost,
        'assets_percentage': assets_percentage*100,
        'skills_percentage': skills_percentage*100,
        'events_percentage': events_percentage*100,
        'hand_slot': hand_slot,
        'arcane_slot': arcane_slot,
        'body_slot': body_slot,
        'accessory_slot': accessory_slot,
        'ally_slot': ally_slot,
        'skill_willpower': skill_willpower,
        'skill_agility': skill_agility,
        'skill_combat': skill_combat,
        'skill_intellect': skill_intellect,
        'skill_wild': skill_wild,
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
        'inv_skill_wild': inv_skill_wild
        }
    # print(inv_exclusion_recs)
    # print("Mean cost: {:f}".format(all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['mean_cost'].mean()))
    # print("Assets:  {:f}".format(all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['asset_percentages'].mean()))
    # print("Events:  {:f}".format(all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['event_percentages'].mean()))
    # print("Skills:  {:f}".format(all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['skill_percentages'].mean()))
    # print("Treachery:  {:f}".format(all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]]['treachery_percentages'].mean()))

    # deck_to_compare_with_info = pd.DataFrame.from_dict(deck_to_compare['slots'][0],orient='index').join(card_cycles[['code_str','name','type_code','cost']].set_index('code_str'))
    # type_distribution = deck_to_compare_with_info.groupby('type_code')[0].sum()
    # type_distribution = type_distribution / type_distribution.sum()
    # #type_distribution

    # deck_to_compare_with_info['w_costs']=deck_to_compare_with_info['cost'] * deck_to_compare_with_info[0]
    # mean_cost = deck_to_compare_with_info[~deck_to_compare_with_info.cost.isnull()]['w_costs'].sum() / deck_to_compare_with_info[~deck_to_compare_with_info.cost.isnull()][0].sum()

    # assets_percentage_in_deck = type_distribution['asset'] if 'asset' in type_distribution.index else 0
    # treachery_percentage_in_deck = type_distribution['treachery'] if 'treachery' in type_distribution.index else 0
    # skill_percentage_in_deck = type_distribution['skill'] if 'skill' in type_distribution.index else 0
    # event_percentage_in_deck = type_distribution['event'] if 'event' in type_distribution.index else 0

    # print("Mean cost: {:f}".format(mean_cost))
    # print("Assets:  {:f}".format(assets_percentage_in_deck))
    # print("Events:  {:f}".format(event_percentage_in_deck))
    # print("Skills:  {:f}".format(skill_percentage_in_deck))
    # print("Treachery:  {:f}".format(treachery_percentage_in_deck))



    deck = pd.DataFrame.from_dict(
        deck_to_compare.loc[:,'slots'][0], orient='index', columns=['count']).join(
            card_cycles[['code_str','name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp']].set_index('code_str')).join(
                inv_exclusion_recs[['Coocurrence']]).join(
                    exclusion_recs[['Jaccard Score']])
    
    deck_info =deck_to_compare[['investigator_name', 'investigator_code', 'name', 'taboo_id', 'date_creation', 'date_update', 'xp']].to_dict(orient='index')[0]
    deck_info['investigator_code'] = str(deck_info['investigator_code']).zfill(5)
    deck_info['date_creation'] = deck_info['date_creation'][0:10]
    deck_info['date_update'] = deck_info['date_update'][0:10]
    deck_info['xp'] = "{:0.0f}".format(deck['xp'].sum())
    deck_info['total_cards'] = deck['count'].sum()
    deck_info['inv_deck_count'] = all_decks_clean[all_decks_clean['investigator_name']==deck_to_compare['investigator_name'][0]].count()[0]


    deck['color'] = deck['faction_code']
    deck.loc[deck['faction2_code'].notna(),'color']='multi'
    deck = convert_xp_to_str(deck)
    deck = deck.fillna("-")

    inclusion_recs['color'] = inclusion_recs['faction_code']
    inclusion_recs.loc[inclusion_recs['faction2_code'].notna(),'color']='multi'
    inclusion_recs = convert_xp_to_str(inclusion_recs)
    inclusion_recs = inclusion_recs.fillna("-")

    inv_inclusion_recs['color'] = inv_inclusion_recs['faction_code']
    inv_inclusion_recs.loc[inv_inclusion_recs['faction2_code'].notna(),'color']='multi'
    inv_inclusion_recs = convert_xp_to_str(inv_inclusion_recs)
    inv_inclusion_recs = inv_inclusion_recs.fillna("-")

    return render_template('deck/view.html', deck=deck.to_dict('index'), inclusion_recs=inclusion_recs.to_dict('index'), deck_statistics=deck_statistics, deck_info=deck_info)

def convert_xp_to_str(deck):
    deck.loc[:,'xp'] = deck.loc[:,'xp'].to_frame().applymap(lambda x: "{:0.0f}".format(x) if x>0 else '')
    return deck
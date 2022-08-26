from arkhrec.data_helpers import filter_cards_in_collection, get_all_cards, get_all_decks, get_all_investigators, get_analysed_card_codes, get_card_investigator_cooccurrences, get_card_jaccard_scores, get_duplicates_unique_code, get_analysed_cards, get_collection, get_investigator_deck_statistics
import arkhrec.general_helpers
import pandas as pd
import math
import ast
import collections
import ast

bonus_experience = {
    'Father Mateo': 5
}

def build_average_deck(investigator, analysed_cards, deck_statistics):
    all_cards = get_all_cards()
    all_decks = get_all_decks()

    inv_assets_percentage = deck_statistics['inv_assets_percentage']/100
    inv_events_percentage = deck_statistics['inv_events_percentage']/100

    investigator_id = investigator.index[0]

    deck_reqs = investigator['deck_requirements'][0].split(',')
    
    card_reqs_codes = ['01000']
    for req in deck_reqs:
        req_tuple = req.split(':',1)
        if(req_tuple[0]=='size'):
            deck_size = int(req_tuple[1])
        elif (req_tuple[0].strip()=='card'):
            card_reqs_codes.append(req_tuple[1].split(':')[0])
                
       
    card_reqs = all_cards[all_cards['code_str'].isin(card_reqs_codes)]
    card_reqs_quants = card_reqs.groupby('type_code')['quantity'].sum()

    deck_size_selected = collections.Counter()
    faction_selected = collections.Counter()
    two_factions_selected = collections.Counter()
    alternate_front = collections.Counter()
    alternate_back = collections.Counter()
    option_selected = collections.Counter()

    choice_decks=all_decks[all_decks['investigator_name'] == investigator['name'][0]]

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

    inv_card_deck = all_cards.set_index('code_str').loc[investigator_id]

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

    card_cycles_pool = analysed_cards.drop(card_reqs.set_index('code_str').index, errors='ignore')
    card_cycles_pool = filter_cards_in_collection(card_cycles_pool)
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

    return [average_deck, card_reqs]

def cards_valid_for_investigator(card_cycles_pool, deck_options, single_faction_selected='', multi_faction_selected=[], apply_limits=True):
    import pandas as pd

    card_pools=[]
    for do in deck_options:
        if 'faction' in do and 'level' in do and 'limit' not in do:
                restriction_pool = card_cycles_pool[(card_cycles_pool['faction_code'].isin(do['faction'])) & (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1)))]
                card_pools.append(restriction_pool)
                # Mark main factions to define factions for Dunwich splash    
                main_factions = do['faction']
        elif 'faction' in do and 'level' in do and 'limit' in do:
            restriction_pool = card_cycles_pool[(card_cycles_pool['faction_code'].isin(do['faction'])) & card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1))]
            if apply_limits:
                restriction_pool = restriction_pool.sort_values('inv_occurrence', ascending=False).head(do['limit'])    
            card_pools.append(restriction_pool)
            # filter_limits.append({'factions': do['faction'], 'level': do['level'], 'limit': do['limit']})
        elif 'level' in do and 'faction' not in do and 'limit' in do:
            factions = ['guardian', 'mystic', 'seeker', 'rogue', 'survivor', 'neutral']
            filter_classes = factions
            for f in main_factions:
                filter_classes.remove(f)
            restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'].isin(filter_classes)) | (card_cycles_pool['faction2_code'].isin(filter_classes)) | (card_cycles_pool['faction3_code'].isin(filter_classes)) ) & card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1))]

            if apply_limits:
                restriction_pool = restriction_pool.sort_values('inv_occurrence', ascending=False).head(do['limit'])
            card_pools.append(restriction_pool)

        elif 'name' in do:
            if do['name'] == 'Secondary Class':
                restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'] == single_faction_selected)| (card_cycles_pool['faction2_code'] == single_faction_selected) | (card_cycles_pool['faction3_code'] == single_faction_selected) ) & (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1))) & (card_cycles_pool['type_code'].isin(do['type']))]
                if 'limit' in do and 'type' in do:
                    restriction_pool = restriction_pool[restriction_pool["type_code"]==do['type']]
                    if(apply_limits):
                        restriction_pool = restriction_pool.sort_values('inv_occurrence', ascending=False).head(do['limit'])
                elif 'limit' in do and 'type' not in do:
                    if(apply_limits):
                        restriction_pool = restriction_pool.sort_values('inv_occurrence', ascending=False).head()
                card_pools.append(restriction_pool)
            elif do['name'] == "Class Choice":
                if do['id'] == 'faction_1':
                    restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'] == multi_faction_selected[0]) | (card_cycles_pool['faction2_code'] == multi_faction_selected[0]) | (card_cycles_pool['faction3_code'] == multi_faction_selected[0]) ) & (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1)))]  
                elif do['id'] == 'faction_2':
                    restriction_pool = card_cycles_pool[((card_cycles_pool['faction_code'] == multi_faction_selected[1]) | (card_cycles_pool['faction2_code'] == multi_faction_selected[1]) | (card_cycles_pool['faction3_code'] == multi_faction_selected[1]) )& (card_cycles_pool['xp'].isin(range(do['level']['min'], do['level']['max']+1)))]
                card_pools.append(restriction_pool)

    card_pool = pd.concat(card_pools)

    card_pool = card_pool.loc[card_pool.astype(str).drop_duplicates().index]
    card_pool.loc[:,'deck_limit'] = pd.to_numeric(card_pool['deck_limit'], errors='coerce')
    
    return card_pool


def remove_duplicates_from_deck(deck_to_compare):
    duplicates = get_duplicates_unique_code()
    analysed_card_codes = get_analysed_card_codes()
    duplicates_in_deck = duplicates.loc[list((set(deck_to_compare['slots'][0].keys()) & set(duplicates.index)))]
    deck_to_compare_sub = deck_to_compare.copy()    
    deck_to_compare_sub.loc[:,'slots'][0] = {duplicates_in_deck.loc[k]['unique_code'] if k in duplicates_in_deck.index else k:v for k,v in deck_to_compare['slots'][0].items()}
    deck_to_compare_clean = deck_to_compare_sub.copy()
    deck_to_compare_clean.loc[:,'slots'][0] = {card: value for (card,value) in deck_to_compare_sub['slots'][0].items() if card in analysed_card_codes.index}

    return [deck_to_compare_clean, deck_to_compare_sub]

def get_recommendations_for_deck(deck_to_compare):
    card_jaccard_score = get_card_jaccard_scores()
    all_cards = get_all_cards()
    inv_cooc_ratio = get_card_investigator_cooccurrences()

    [deck_to_compare_clean, deck_to_compare] = remove_duplicates_from_deck(deck_to_compare)
    # Fetch the jaccard scores for the cards in the deck
    deck_jaccards = card_jaccard_score[deck_to_compare_clean['slots'][0].keys()]
    # Sum the jaccard scores for each card of the deck
    recommendations = deck_jaccards.sum(axis=1).sort_values(ascending=False)

    # Get presence in investigator
    presence_in_investigators = inv_cooc_ratio.loc[deck_to_compare['investigator_name'][0],:].transpose().to_frame('Presence')
    presence_in_investigators.loc[:,'Presence'] = presence_in_investigators.applymap(lambda x: "{:0.0%}".format(x))

    # See possible inclusions (drops cards already in deck)
    cards_not_in_deck = recommendations.drop(deck_to_compare_clean['slots'][0].keys()).to_frame('Jaccard Score')
    cards_not_in_deck.loc[:,'Jaccard Score'] = cards_not_in_deck.applymap(lambda x: "{:0.2f}".format(x))
    cards_not_in_deck = cards_not_in_deck.join(all_cards[['code_str','name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code','xp']].set_index('code_str'))

    # Keeps only assets, events and skills (removes treacheries, enemies, locations, ...)
    cards_not_in_deck = cards_not_in_deck[cards_not_in_deck['type_code'].isin(['asset','event', 'skill'])][['name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp', 'Jaccard Score']]
    presence_cards_not_in_deck = presence_in_investigators[~presence_in_investigators.index.isin(deck_to_compare['slots'][0].keys())].join(all_cards[['code_str','name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp']].set_index('code_str'))
    cards_not_in_deck = cards_not_in_deck.join(presence_cards_not_in_deck['Presence'])

    # Removes cards not allowed for deck
    # Gets deck options (if applicable, e.g. off-class faction choice)
    m = deck_to_compare.meta[0]

    ms=['','']
    fs=[]
    if m:
        m = ast.literal_eval(m)
        if 'faction_selected' in m:
            fs = m['faction_selected']
        if 'faction_1' in m:
            ms[0] = m['faction_1']
        if 'faction_2' in m:
            ms[1] = m['faction_2']

    investigator_card = all_cards.set_index('code_str').loc[str(deck_to_compare['investigator_code'][0]).zfill(5)]
    allowed_card_pool = cards_valid_for_investigator(all_cards, investigator_card.deck_options, single_faction_selected=fs, multi_faction_selected=ms, apply_limits=False).set_index('code_str')

    cards_not_in_deck = cards_not_in_deck.loc[cards_not_in_deck.index & allowed_card_pool.index]

    # Prepares for view
    cards_not_in_deck = arkhrec.general_helpers.set_color(cards_not_in_deck)
    cards_not_in_deck = arkhrec.general_helpers.convert_xp_to_str(cards_not_in_deck)
    cards_not_in_deck = cards_not_in_deck.fillna("-")
    cards_not_in_deck['cycle'] = cards_not_in_deck.apply(arkhrec.general_helpers.set_cycle, axis=1)
    cards_not_in_deck = filter_cards_in_collection(cards_not_in_deck)
    
    # Gets jaccard score and presence for cards in deck
    cards_in_deck = recommendations[deck_to_compare_clean['slots'][0].keys()].to_frame('Jaccard Score')

    cards_in_deck.loc[:,'Jaccard Score'] = cards_in_deck.applymap(lambda x: "{:0.2f}".format(x))
    presence_cards_in_deck = presence_in_investigators[presence_in_investigators.index.isin(deck_to_compare['slots'][0].keys())].join(all_cards[['code_str','name','pack_code', 'faction_code']].set_index('code_str')).sort_values(by=presence_in_investigators.columns[0],ascending=True)


    cards_in_deck = pd.DataFrame.from_dict(
        deck_to_compare.loc[:,'slots'][0], orient='index', columns=['count']).join(
            all_cards[['code_str','name', 'pack_code', 'faction_code', 'faction2_code', 'faction3_code','slot','type_code', 'xp', 'myriad']].set_index('code_str')).join(
                presence_cards_in_deck[['Presence']]).join(
                    cards_in_deck[['Jaccard Score']])

    # Prepares for view
    cards_in_deck = arkhrec.general_helpers.set_color(cards_in_deck)
    cards_in_deck = arkhrec.general_helpers.convert_xp_to_str(cards_in_deck)
    cards_in_deck = cards_in_deck.fillna("-")
    cards_in_deck['cycle'] = cards_in_deck.apply(arkhrec.general_helpers.set_cycle, axis=1)

    return [cards_in_deck, cards_not_in_deck, deck_to_compare]

def calculate_deck_statistics(deck_to_compare):
    all_cards = get_all_cards()

    deck_to_compare_with_info = pd.DataFrame.from_dict(deck_to_compare['slots'][0],orient='index').join(
            all_cards[['code_str','name','type_code','cost',"skill_willpower", "skill_agility", "skill_combat", "skill_intellect", "skill_wild", "slot"]].set_index(
            'code_str'))

    deck_to_compare_with_info.loc[:,['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']]=deck_to_compare_with_info[['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']].multiply(deck_to_compare_with_info[0],axis='index')
    pips_sum = deck_to_compare_with_info[['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']].sum()
    slots_count = deck_to_compare_with_info.groupby('slot')[0].sum()

    type_distribution = deck_to_compare_with_info.groupby('type_code')[0].sum()
    type_distribution = type_distribution / type_distribution.sum()

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


    investigator = get_all_investigators().loc[str(int(deck_to_compare['investigator_code'])).zfill(5)].to_frame().transpose()

    investigator_deck_statistics = get_investigator_deck_statistics(investigator)

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
        'inv_mean_cost': investigator_deck_statistics['inv_mean_cost'],
        'inv_assets_percentage': investigator_deck_statistics['inv_assets_percentage'],
        'inv_events_percentage': investigator_deck_statistics['inv_events_percentage'],
        'inv_skills_percentage': investigator_deck_statistics['inv_skills_percentage'],
        'inv_hand_slot': investigator_deck_statistics['inv_hand_slot'],
        'inv_arcane_slot': investigator_deck_statistics['inv_arcane_slot'],
        'inv_body_slot': investigator_deck_statistics['inv_body_slot'],
        'inv_accessory_slot': investigator_deck_statistics['inv_accessory_slot'],
        'inv_ally_slot': investigator_deck_statistics['inv_ally_slot'],
        'inv_skill_willpower': investigator_deck_statistics['inv_skill_willpower'],
        'inv_skill_agility': investigator_deck_statistics['inv_skill_agility'],
        'inv_skill_combat': investigator_deck_statistics['inv_skill_combat'],
        'inv_skill_intellect': investigator_deck_statistics['inv_skill_intellect'],
        'inv_skill_wild': investigator_deck_statistics['inv_skill_wild']
        }

    return deck_statistics

def get_deck_info(deck_to_compare, cards_in_deck):
    all_decks = get_all_decks()
    deck_info =deck_to_compare[['investigator_name', 'investigator_code', 'name', 'taboo_id', 'date_creation', 'date_update', 'xp']].to_dict(orient='index')[0]
    deck_info['investigator_code'] = str(deck_info['investigator_code']).zfill(5)
    deck_info['date_creation'] = deck_info['date_creation'][0:10]
    deck_info['date_update'] = deck_info['date_update'][0:10]
    cards_in_deck['total_xp'] = cards_in_deck['xp'] * cards_in_deck['count']
    cards_in_deck.loc[cards_in_deck['myriad']==1, 'total_xp'] = cards_in_deck.loc[cards_in_deck['myriad']==1,'xp']

    deck_info['xp'] = "{:0.0f}".format(cards_in_deck[cards_in_deck['total_xp']!='-']['total_xp'].astype(int).sum())
    deck_info['total_cards'] = cards_in_deck['count'].sum()
    deck_info['inv_deck_count'] = all_decks[all_decks['investigator_name']==deck_to_compare['investigator_name'][0]].count()[0]

    return deck_info

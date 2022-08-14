import pandas as pd

from datetime import date, timedelta
import functools
import operator
import collections
import math
import operator

def run():

    ############################################################################################################################
    ####  Constants definition                                                                                              ####
    ############################################################################################################################
    MINIMUM_FREQUENCY = 20

    [all_decks, card_cycles, duplicates] = read_decks_and_cards()

    ############################################################################################################################
    ####   Treat decks to include new variables, remove duplicates, etc                                                     ####
    ############################################################################################################################

    all_decks_clean = treat_decks(all_decks, card_cycles, duplicates)

    ############################################################################################################################
    ####   Calculate card frequencies in each deck (summing if repeated) & remove little used cards                         ####
    ############################################################################################################################

    card_frequencies = pd.DataFrame(dict(functools.reduce(operator.add,
                            map(collections.Counter, all_decks_clean["slots"]))).items())

    
    card_frequencies_clean = card_frequencies[card_frequencies[1]>MINIMUM_FREQUENCY]
    print("Card frequency - total")
    print(card_frequencies.describe())
    print("Card frequency - after cleaning with limit = {:d}".format(MINIMUM_FREQUENCY))
    print(card_frequencies_clean.describe())

    card_frequencies_clean.columns = ['card', 'count']
    card_frequencies_clean = card_frequencies_clean.set_index('card')

    ############################################################################################################################
    ####   Create vector with decks containing only selected cards and without the number of cards in deck                  ####
    ############################################################################################################################
    # !!REFACTOR
    # should this be a dictionary or only an array? Seems to me an array would be better than filling it with 1s just for counting...
    
    all_decks_clean.loc[:,'slots_count'] = all_decks_clean.apply(lambda deck: {card: 1 for (card,value) in 
                                            deck['slots'].items() if card in card_frequencies_clean.index},
                                            axis=1)

    # Export to file
    print("Exporting all_decks_clean and card_frequencies_clean")
    all_decks_clean.to_pickle('datafiles/all_decks_clean.pickle')
    card_frequencies_clean.to_pickle('datafiles/card_frequencies_clean.pickle')
    
    ############################################################################################################################
    ####   Calculate the card coocurrence value (number of times a card appears together with another)                      ####
    ############################################################################################################################
    
    card_frequencies_only = card_frequencies_clean.index
    results = dict()
    for card in card_frequencies_only:
        # !!REFACTOR
        # This could be at least 2x faster, if I only calculate coocurrence once per pair (I am calculating twice per pair)
        # Since it is running quickly for now, I will leave it be
        print('.',end='',flush=True)
        decks_with_card = all_decks_clean[all_decks_clean.slots.apply(lambda cards: card in cards)]
        
        # Summing the number of cards
        # I could do this with map reduce, but I honestly have a hard time everytime I have to understand these lines
        # Did it with a for loop instead
        # If I had to calculate the coocurence considering the count of each card in the deck, I could switch 'slots_count' for 'slots' below
        #results[card] = dict(functools.reduce(operator.add,map(collections.Counter, decks_with_card["slots_count"])))
        
        # Counting the number of cards by card (increments a counter everytime a card appears with another)
        results[card] = collections.Counter()
        for d in decks_with_card["slots_count"]:
            results[card] += collections.Counter({x: 1 for x in d})
    card_cooc = pd.DataFrame(results).fillna(0)
    card_cooc.to_pickle("datafiles/card_cooc.pickle")
    
    ############################################################################################################################
    ####   Calculate the investigator x card coocurrence value (times a card appears together with an investigator)         ####
    ############################################################################################################################

    # List all the investigators (by name, because there are duplicate codes e.g. book investigators)
    investigators = all_decks_clean.groupby(['investigator_name'])['investigator_name'].count()

    # Calculate the card occurence value per investigator
    card_frequencies_only = card_frequencies_clean.index
    results = dict()
    for investigator in investigators.index:
        print('.',end='')
    #     print(investigator)
        decks_with_investigator =  all_decks_clean[all_decks_clean['investigator_name']==investigator]
        
        # Counting the number of cards
        results[investigator] = collections.Counter()
        for d in decks_with_investigator["slots_count"]:
            results[investigator] += collections.Counter({x: 1 for x in d})

    inv_cooc = pd.DataFrame(results).fillna(0).transpose()

    ############################################################################################################################
    ####   Define functions to calculate cross cooc ratio and jaccard distance,  to be used on the apply                    ####
    ############################################################################################################################
    #!!REFACTOR
    # This feels very ugly and wrong. Probably have to refactor this first

    # def calculate_ppmi(row):
    #     for col in row.index:
    #         ki = card_frequencies.loc[row.name]['count']
    #         kj = card_frequencies.loc[col]['count']
    #         kij = card_cooc.loc[row.name][col]
    #         log_arg = total_cards*kij / (ki*kj)
    #         ppmi = math.log2(log_arg) if log_arg>0 else 0
    #         row[col] = ppmi
    #     return row

    def calculate_jaccard_similarity(row):
        for col in row.index:
            count_ij = card_cooc.loc[row.name][col]
            count_i = card_cooc.loc[row.name][row.name]
            count_j = card_cooc.loc[col][col]
            union = count_i+count_j-count_ij
            row[col] = count_ij / union
        print('.',end='',flush=True)
        return row

    def calculate_simple_coocurrence(row):
        for col in row.index:
            count_ij = card_cooc.loc[row.name][col]
            count_j = card_cooc.loc[col][col]
            row[col] = count_ij / count_j
        print('.',end='', flush=True)
        return 
        
    ############################################################################################################################
    ####   Calculate Jaccard similarity and Coocurrence Ratio (this takes a while)                                          ####
    ############################################################################################################################
    card_jaccard_score = card_cooc.copy()
    card_cooc_ratio = card_cooc.copy()
    
    print("\n Jaccard")
    card_jaccard_score.apply(calculate_jaccard_similarity, axis=1)
    print("\n Done")
    print("\n Simple ratio") 
    card_cooc_ratio.apply(calculate_simple_coocurrence, axis=1)
    print("\n Done")

    ############################################################################################################################
    ####   Calculate the card per investigator ocurrence ratio                                                              ####
    ############################################################################################################################
    investigators.columns = ['number_of_decks']
    inv_cooc_ratio = inv_cooc.copy()
    inv_cooc_ratio = inv_cooc_ratio.join(investigators)
    
    # Divides the number of times each card appear with each investigator by the total of decks per investigator
    inv_cooc_ratio = inv_cooc_ratio.iloc[:,:-1].div(inv_cooc_ratio.iloc[:,-1:].squeeze(), axis=0)

    
    card_cooc_ratio.to_pickle("datafiles/card_cooc_ratio.pickle")
    card_jaccard_score.to_pickle("datafiles/card_jaccard_score.pickle")
    inv_cooc_ratio.to_pickle("datafiles/inv_cooc_ratio.pickle")


def read_decks_and_cards():
    ############################################################################################################################
    ####   Both of these readings should be done in another place - REFACTOR                                                ####
    ############################################################################################################################
    # !!REFACTOR
    # Read decks
    all_decks = pd.read_pickle("datafiles/all_decks.pickle")
    
    # Read cards
    card_cycles_array = []
    from pathlib import Path

    # chage this path
    files = Path("datafiles/cards").glob("**/*.json")
    print("Reading cards db")
    for file in files:
        card_cycle_pack = pd.read_json(file)
        card_cycles_array.append(card_cycle_pack)
        print('.',end='',flush=True)
    print("\nDone")

    card_cycles = pd.concat(card_cycles_array, ignore_index=True)

    # Change the format of the "code" variable from int to string
    # This was automatically infered by the "read_json" function, so there is maybe a more intelligente way to solve this at read-time
    card_cycles['code_str'] = card_cycles['code'].astype(str).apply(str.zfill, args=[5])
    card_cycles.set_index('code_str')

    duplicates = card_cycles[~card_cycles['duplicate_of'].isnull()][['duplicate_of','code_str']].set_index('code_str')
    duplicates['duplicate_of_str'] = duplicates['duplicate_of'].to_frame().applymap(lambda x: "{:05.0f}".format(x))

    # Export to file
    duplicates.to_pickle("datafiles/duplicates.pickle")
    card_cycles.to_pickle("datafiles/card_cycles.pickle")

    return [all_decks, card_cycles, duplicates]
    ########################################### END OF READINGS ##################################################################

def treat_decks(all_decks, card_cycles, duplicates):
    new_slots = []
    mean_costs = []
    asset_percentages = []
    treachery_percentages = []
    skill_percentages = []
    event_percentages = []
    willpower_total = []
    combat_total = []
    intellect_total = []
    agility_total = []
    wild_total = []
    hand_slot_total = []
    arcane_slot_total = []
    accessory_slot_total = []
    body_slot_total = []
    ally_slot_total = []

    # Remove decks that are copies / evolutions of one another and get only the last version of it
    all_decks_clean = all_decks[pd.isnull(all_decks['next_deck'])]

    print('Cleaning decks...')
    for d in all_decks_clean['slots']:
        print('.',end='',flush=True)
        # Remove duplicates from this deck
        duplicates_in_deck = duplicates.loc[list((set(d.keys()) & set(duplicates.index)))]
        deck_no_duplicates = {duplicates_in_deck.loc[k]['duplicate_of_str'] if k in duplicates_in_deck.index else k:v for k,v in d.items()}
        new_slots.append(deck_no_duplicates)

        # Calculate deck info (type distribution, cost, etc)
        # deck_cards_with_info = pd.DataFrame.from_dict(deck_no_duplicates,orient='index').join(card_cycles[['code_str','name','type_code','cost']].set_index('code_str'))
        deck_cards_with_info = pd.DataFrame.from_dict(deck_no_duplicates,orient='index').join(
            card_cycles[['code_str','name','type_code','cost',"skill_willpower", "skill_agility", "skill_combat", "skill_intellect", "skill_wild", "slot"]].set_index(
            'code_str'))

        deck_cards_with_info.loc[:,['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']]=deck_cards_with_info[['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']].multiply(deck_cards_with_info[0],axis='index')
        pips_sum = deck_cards_with_info[['skill_willpower','skill_agility', 'skill_combat', 'skill_intellect', 'skill_wild']].sum()
        slots_count = deck_cards_with_info.groupby('slot')[0].sum()
        # deck_cards_with_info.groupby('type_code').count()['name']
        type_distribution = deck_cards_with_info.groupby('type_code')[0].sum()
        type_distribution = type_distribution / type_distribution.sum()
        #type_distribution

        deck_cards_with_info['w_costs']=deck_cards_with_info['cost'] * deck_cards_with_info[0]
        mean_cost = deck_cards_with_info[~deck_cards_with_info.cost.isnull()]['w_costs'].sum() / deck_cards_with_info[~deck_cards_with_info.cost.isnull()][0].sum()
        mean_costs.append(mean_cost)
        asset_percentages.append(type_distribution['asset'] if 'asset' in type_distribution.index else 0)
        treachery_percentages.append(type_distribution['treachery'] if 'treachery' in type_distribution.index else 0)
        skill_percentages.append(type_distribution['skill'] if 'skill' in type_distribution.index else 0)
        event_percentages.append(type_distribution['event'] if 'event' in type_distribution.index else 0)
        willpower_total.append(pips_sum['skill_willpower'] if 'skill_willpower' in pips_sum.index else 0)
        combat_total.append(pips_sum['skill_combat'] if 'skill_combat' in pips_sum.index else 0)
        intellect_total.append(pips_sum['skill_intellect'] if 'skill_intellect' in pips_sum.index else 0)
        agility_total.append(pips_sum['skill_agility'] if 'skill_agility' in pips_sum.index else 0)
        wild_total.append(pips_sum['skill_wild'] if 'skill_wild' in pips_sum.index else 0)
        slots_count = deck_cards_with_info.groupby('slot')[0].sum()
        slots_count = slots_count.index * slots_count
        slots_count = slots_count.str.cat().replace("Hand x2", "HandHand").replace("Arcane x2", "ArcaneArcane").replace("Accessory x2", "AccessoryAccessory").replace("Body x2", "BodyBody").replace("Ally x2", "AllyAlly")
        hand_slot_total.append(slots_count.count("Hand"))
        arcane_slot_total.append(slots_count.count("Arcane"))
        accessory_slot_total.append(slots_count.count("Accessory"))
        body_slot_total.append(slots_count.count("Body"))
        ally_slot_total.append(slots_count.count("Ally"))
    print("\n Done")
    all_decks_clean.loc[:,'slots'] = new_slots
    all_decks_clean.loc[:,'asset_percentages'] = asset_percentages
    all_decks_clean.loc[:,'treachery_percentages'] = treachery_percentages
    all_decks_clean.loc[:,'skill_percentages'] = skill_percentages
    all_decks_clean.loc[:,'event_percentages'] = event_percentages
    all_decks_clean.loc[:,'mean_cost'] = mean_costs
    all_decks_clean.loc[:,'skill_willpower'] = willpower_total
    all_decks_clean.loc[:,'skill_combat'] = combat_total
    all_decks_clean.loc[:,'skill_agility'] = agility_total
    all_decks_clean.loc[:,'skill_intellect'] = intellect_total
    all_decks_clean.loc[:,'skill_wild'] = wild_total
    all_decks_clean.loc[:,'hand_slot'] = hand_slot_total
    all_decks_clean.loc[:,'arcane_slot'] = arcane_slot_total
    all_decks_clean.loc[:,'accessory_slot'] = accessory_slot_total
    all_decks_clean.loc[:,'body_slot'] = body_slot_total
    all_decks_clean.loc[:,'ally_slot'] = ally_slot_total

    return all_decks_clean



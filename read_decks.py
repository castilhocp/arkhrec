import pandas as pd

import functools
import operator
import collections
import operator

import logging

# Script that runs periodically, fetches new decks from Arkham DB and calculates cooccurrence metrics

def read_decks_from_arkhamdb():

    root = logging.getLogger()
    root.handlers = []
    logging.basicConfig(filename="cooccurrences_update_log")

    root.setLevel(logging.INFO)

    # handler = logging.StreamHandler(sys.stdout)
    # handler.setLevel(logging.DEBUG)
    # handler.setFormatter(formatter)
    # root.addHandler(handler)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    

    ############################################################################################################################
    ####  Creates backups                                                                                               ####
    ############################################################################################################################
    from datetime import date

    FILES = [
        'all_decks.pickle',
        'all_decks_clean.pickle',
        'duplicates.pickle',
        'all_cards.pickle',
        'analysed_card_frequencies.pickle',
        'cooccurrences_calculated.pickle',
        'inv_cooccurrences_calculated.pickle'
    ]


    import shutil

    logging.info("Backing up files:")
    for f in FILES:
        filename = 'datafiles/'+f
        backup_name = 'backups/' + f +"."+ date.today().strftime("%d")
        shutil.copyfile(filename, backup_name)
        logging.info("File: {}; Backup: {}".format(filename,backup_name))

    ############################################################################################################################
    ####  Reads decks                                                                                                       ####
    ############################################################################################################################
    all_decks = pd.read_pickle("datafiles/all_decks.pickle")

    ############################################################################################################################
    ####  Fetches decks from today from ArkhamDB                                                                            ####
    ############################################################################################################################
    # Loads decks from day
    from urllib.error import HTTPError
    from datetime import datetime, date, timedelta

    last_day_read = datetime.strptime(all_decks['date_creation'].max()[:10],'%Y-%m-%d').date()
    date_list = [date.today() - timedelta(days=x+1) for x in range((date.today() - last_day_read).days - 1)]

    if(len(date_list)==0):
        logging.info('No new days to fecth. Exiting')
        exit()
    else:
        url = "http://arkhamdb.com/api/public/decklists/by_date/"
        logging.info("Fetching decks from ArkhamDB from: {0} to {1}".format(date_list[len(date_list)-1], date_list[0]))

        all_decks_list = []
        for dr in date_list:
            try:
                logging.info("Fetching from: {0}".format(url+dr.strftime('%Y-%m-%d')))
                decks = pd.read_json(url+dr.strftime('%Y-%m-%d'))
            except HTTPError as err:
                logging.error("Caught HTTP error on url: {}".format(url+dr.strftime('%Y-%m-%d')))
                logging.error(err)
                exit()
            except ValueError as err:
                logging.error("Caught Value error on url: {}".format(url+dr.strftime('%Y-%m-%d')))
                logging.error(err)
                exit()         
            all_decks_list.append(decks)

        logging.info("Done fetching")

        decks_of_day = pd.concat(all_decks_list, ignore_index=True)

        if(len(decks_of_day)>0):
            logging.info("{} decks read. Need to update cooccurrences".format(len(decks_of_day)))

            all_decks = pd.concat([all_decks, decks_of_day], ignore_index=True)

            ############################################################################################################################
            ####  Reads cards and packs                                                                                             ####
            ############################################################################################################################
            MINIMUM_FREQUENCY = 5
            [card_cycles, duplicates, all_packs] = read_cards_and_packs()

            ############################################################################################################################
            ####   Treat decks to include new variables, remove duplicates, etc                                                     ####
            ###########################################################################################################################

            decks_of_day_clean = treat_decks(decks_of_day, card_cycles, duplicates)

            ############################################################################################################################
            ####   Calculate card frequencies in each deck (summing if repeated) & remove little used cards                         ####
            ############################################################################################################################

            all_decks_clean = pd.read_pickle('datafiles/all_decks_clean.pickle')
            logging.info("Previous all decks clean length: {}".format(len(all_decks_clean)))

            all_decks_clean = pd.concat([all_decks_clean, decks_of_day_clean])

            logging.info("Decks read: {}".format(len(decks_of_day_clean)))
            logging.info("New all decks clean length: {}".format(len(all_decks_clean)))

            outdated_decks = all_decks_clean[all_decks_clean['id'].isin(all_decks_clean['previous_deck'].dropna())]
            logging.info("Outdated decks: {}".format(len(outdated_decks)))

            if len(outdated_decks)>0:
                # drops decks that were updated
                all_decks_clean=all_decks_clean.drop(outdated_decks)
                # will have to rerun all the cooccurrences (it will take time...)
                decks_to_analyse = all_decks_clean
                logging.info("Outdated decks - setting recommender to recalculate for all decks")
            else:
                # no decks updated, can run cooccurrences only for new decks and new cards
                decks_to_analyse = decks_of_day_clean
                logging.info("No outdated decks - setting recommender to recalculate only for new decks and cards")


            card_frequencies = pd.DataFrame(dict(functools.reduce(operator.add,
                                    map(collections.Counter, all_decks_clean["slots"]))).items())

            analysed_card_frequencies = card_frequencies[card_frequencies[1]>MINIMUM_FREQUENCY]
            logging.info("Card frequency - total")
            logging.info(card_frequencies.describe())
            logging.info("Card frequency - after cleaning with limit = {:d}".format(MINIMUM_FREQUENCY))
            logging.info(analysed_card_frequencies.describe())

            all_decks_clean.loc[:,'slots_count'] = all_decks_clean.apply(lambda deck: {card: 1 for (card,value) in 
                                                deck['slots'].items() if card in analysed_card_frequencies.index},
                                                axis=1)

            analysed_card_frequencies.columns = ['code_str', 'appearances']
            analysed_card_frequencies = analysed_card_frequencies.set_index('code_str')

            analysed_card_frequencies_old = pd.read_pickle('datafiles/analysed_card_frequencies.pickle')

            old_cards = analysed_card_frequencies_old.index
            new_cards = list(set(analysed_card_frequencies.index) - set(analysed_card_frequencies_old.index))
            logging.info("New cards: {}".format(new_cards))

            ############################################################################################################################
            ####   Create vector with decks containing only selected cards and without the number of cards in deck                  ####
            ############################################################################################################################

            #calculate coocs for new decks only, with old cards
            logging.info("Calculating cooccurrences for new decks...")
            [card_cooccurrences_new_decks, inv_cooccurrences_new_decks] = calculate_cooccurrences(decks_to_analyse, card_cycles, all_packs, old_cards)
            logging.info("Done")

            # read current cooccurrences
            previous_cooccurrences = pd.read_pickle('datafiles/cooccurrences_calculated.pickle')
            previous_inv_cooccurrences = pd.read_pickle('datafiles/inv_cooccurrences_calculated.pickle')

            #calculate coocs for new cards, for all decks
            new_cooccurrences = previous_cooccurrences.add(card_cooccurrences_new_decks, fill_value=0)
            new_inv_cooccurrences = previous_inv_cooccurrences.add(inv_cooccurrences_new_decks, fill_value=0)

            if len(new_cards)>0:
                logging.info("Calculating cooccurrences for new cards...")
                [card_cooccurrences_new_cards, inv_cooccurrences_new_cards] = calculate_cooccurrences(all_decks_clean, card_cycles, all_packs, old_cards, new_cards)
                new_cooccurrences = pd.concat([new_cooccurrences, card_cooccurrences_new_cards])
                new_inv_cooccurrences = pd.concat([new_inv_cooccurrences, inv_cooccurrences_new_cards])
                logging.info("Done")
            else:
                logging.info("No new cards to calculate cooccurrence")

            new_cooccurrences['jaccard'] = new_cooccurrences['cooccurrences']/(new_cooccurrences['occurrences_card1'] + new_cooccurrences['occurrences_card2'] - new_cooccurrences['cooccurrences'])
            new_inv_cooccurrences['presence'] = new_inv_cooccurrences['inv_cooccurrences'] / new_inv_cooccurrences['occurrences_investigator']
            new_inv_cooccurrences['card_occurrences_ratio'] = new_inv_cooccurrences['occurrences_card'] / new_inv_cooccurrences['num_decks']
            new_inv_cooccurrences['synergy'] = new_inv_cooccurrences['presence'] - new_inv_cooccurrences['card_occurrences_ratio']

            # Export to file
            logging.info("Exporting all_decks_clean and card_frequencies_clean")
            all_decks_clean.to_pickle('datafiles/all_decks_clean.pickle')
            analysed_card_frequencies.to_pickle('datafiles/analysed_card_frequencies.pickle')
            new_cooccurrences.to_pickle('datafiles/cooccurrences_calculated.pickle')
            new_inv_cooccurrences.to_pickle('datafiles/inv_cooccurrences_calculated.pickle')
            all_decks.to_pickle('datafiles/all_decks.pickle')

def calculate_cooccurrences(decks, card_cycles, all_packs, card_frequencies_only, new_cards=[]):
    import numpy as np
    indexes_card_pairs = []
    cards_in_deck = pd.DataFrame(dict(functools.reduce(operator.add,
                        map(collections.Counter, decks["slots"]))).items())[0]
    cards_list = list((set(cards_in_deck) & set(card_frequencies_only.values)) | set(new_cards))
    cards_list = np.sort(cards_list)
    if new_cards:
        for f in range(1, len(cards_list)+1):
            for f2 in range(1, len(new_cards)+1):
                indexes_card_pairs.append((min(cards_list[f-1],new_cards[f2-1]), max(cards_list[f-1],new_cards[f2-1])))
    else:
        for f in range(1, len(cards_list)+1):
            for f2 in range(f, len(cards_list)+1):
                indexes_card_pairs.append((cards_list[f-1],cards_list[f2-1]))
        #         print("f-1: {}, f2-1: {}".format(f-1, f2-1))
    mi_indexes = pd.MultiIndex.from_tuples(indexes_card_pairs, names=['card1', 'card2']).drop_duplicates()
    cooccurrences = pd.DataFrame(index=mi_indexes)

    cooccurrences = cooccurrences.join(card_cycles.set_index('code_str')['pack_code'], on='card1').join(card_cycles.set_index('code_str')['pack_code'], on='card2', rsuffix='_2')
    release_dates = { k: datetime.strptime((all_packs[k]['date_release'] if all_packs[k]['date_release'] else "2017-01-01"),'%Y-%m-%d') for k in all_packs.keys()}
    cooccurrences.columns = ['card1_pack', 'card2_pack']

    cooccurrences.loc[cooccurrences.index, 'card1_release_date'] = pd.to_datetime(cooccurrences['card1_pack'].map(release_dates))
    cooccurrences.loc[cooccurrences.index, 'card2_release_date'] = pd.to_datetime(cooccurrences['card2_pack'].map(release_dates))
    cooccurrences.loc[cooccurrences.index,'min_deck_date'] = cooccurrences[['card1_release_date', 'card2_release_date']].max(axis=1)
    def count_cooccurrences(row):
        cooccurrence = len(decks[(decks.slots.apply(lambda cards: row.name[0] in cards)) & (decks.slots.apply(lambda cards: row.name[1] in cards)) & (decks['time_date_update']>row['min_deck_date'])])
        occurrence_card1 = len(decks[(decks.slots.apply(lambda cards: row.name[0] in cards)) & (decks['time_date_update']>row['min_deck_date'])])
        occurrence_card2 = len(decks[(decks.slots.apply(lambda cards: row.name[1] in cards)) & (decks['time_date_update']>row['min_deck_date'])])
        num_decks = len(decks[(decks['time_date_update']>row['min_deck_date'])])
        return [occurrence_card1, occurrence_card2, cooccurrence, num_decks]

    cooccurrences_calculated = cooccurrences.apply(count_cooccurrences, axis=1, result_type='expand')
    cooccurrences_calculated.columns = ['occurrences_card1', 'occurrences_card2', 'cooccurrences', 'num_of_decks']
    cooccurrences_calculated['jaccard'] = cooccurrences_calculated['cooccurrences']/(cooccurrences_calculated['occurrences_card1'] + cooccurrences_calculated['occurrences_card2'] - cooccurrences_calculated['cooccurrences'])
    
    all_investigators = card_cycles[card_cycles['type_code']=="investigator"]

    # There are investigators with multiple codes (e.g. parallel versions, book versions, etc.)
    # Gets the minimum code (that's the "cycle" version)
    # Converts to numeric to find the minimum value
    all_investigators.loc[:,'code'] = pd.to_numeric(all_investigators['code'])
    investigator_unique_codes = all_investigators.groupby('name')['code'].min()
    card_cycles.loc[:,'code'] = pd.to_numeric(card_cycles['code'], errors='coerce')
    investigators = card_cycles[card_cycles['code'].isin(investigator_unique_codes.values)].set_index('name')
    
    investigator_list = decks['investigator_name'].unique()
    investigator_codes = investigators[np.array(investigators.reset_index()['name'].isin(investigator_list))]['code_str']
    indexes_card_pairs = []
    if new_cards:
        for f in range(1, len(investigator_codes)+1):
            for f2 in range(1, len(new_cards)+1):
                indexes_card_pairs.append((investigator_codes[f-1],new_cards[f2-1]))
    else:
        for f in range(1, len(investigator_codes)+1):
            for f2 in range(1, len(cards_list)+1):
                indexes_card_pairs.append((investigator_codes[f-1],cards_list[f2-1]))
    mi_indexes = pd.MultiIndex.from_tuples(indexes_card_pairs, names=['investigator', 'card'])
    investigator_presence = pd.DataFrame(index=mi_indexes)
    investigator_count = decks.groupby('investigator_name').count()['name'].to_frame()

    investigator_presence = investigator_presence.join(investigator_codes.reset_index().set_index('code_str'), on=['investigator'])
    investigator_presence = investigator_presence.join(card_cycles.set_index('code_str')['pack_code'], on='investigator').join(card_cycles.set_index('code_str')['pack_code'], on='card', rsuffix='_2')
    investigator_presence.columns = ['name', 'investigator_pack', 'card_pack']

    investigator_presence.loc[investigator_presence.index, 'investigator_release_date'] = pd.to_datetime(investigator_presence['investigator_pack'].map(release_dates))
    investigator_presence.loc[investigator_presence.index, 'card_release_date'] = pd.to_datetime(investigator_presence['card_pack'].map(release_dates))
    investigator_presence.loc[investigator_presence.index,'min_deck_date'] = investigator_presence[['investigator_release_date', 'card_release_date']].max(axis=1)
    def count_inv_cooccurrences(row):
        inv_cooccurrence = len(decks[(decks['investigator_name']==row['name']) & (decks.slots.apply(lambda cards: row.name[1] in cards)) & (decks['time_date_update']>row['min_deck_date'])])
        occurrence_investigator = len(decks[(decks['investigator_name']==row['name']) & (decks['time_date_update']>row['min_deck_date'])])
        occurrence_card = len(decks[(decks.slots.apply(lambda cards: row.name[1] in cards)) & (decks['time_date_update']>row['min_deck_date'])])
        num_decks = len(decks[(decks['time_date_update']>row['min_deck_date'])])
        return [occurrence_investigator, occurrence_card, inv_cooccurrence, num_decks]

    inv_cooccurrences_calculated = investigator_presence.apply(count_inv_cooccurrences, axis=1, result_type='expand')
    inv_cooccurrences_calculated.columns = ['occurrences_investigator', 'occurrences_card', 'inv_cooccurrences', 'num_decks']

    inv_cooccurrences_calculated['presence'] = inv_cooccurrences_calculated['inv_cooccurrences'] / inv_cooccurrences_calculated['occurrences_investigator']
    inv_cooccurrences_calculated['card_occurrences_ratio'] = inv_cooccurrences_calculated['occurrences_card'] / inv_cooccurrences_calculated['num_decks']
    inv_cooccurrences_calculated['synergy'] = inv_cooccurrences_calculated['presence'] - inv_cooccurrences_calculated['card_occurrences_ratio']

    return [cooccurrences_calculated, inv_cooccurrences_calculated]

def read_cards_and_packs():
    # Read cards
    card_cycles_array = []
    from pathlib import Path

    # chage this path
    files = Path("datafiles/cards").glob("**/*.json")
    logging.info("Reading cards db")
    for file in files:
        card_cycle_pack = pd.read_json(file)
        card_cycles_array.append(card_cycle_pack)
#         logging.info('.',end='',flush=True)
    logging.info("\nDone")

    all_cards = pd.concat(card_cycles_array, ignore_index=True)

    # Change the format of the "code" variable from int to string
    # This was automatically infered by the "read_json" function, so there is maybe a more intelligent way to solve this at read-time
    all_cards['code_str'] = all_cards['code'].astype(str).apply(str.zfill, args=[5])
    all_cards.set_index('code_str')

    duplicates = all_cards[~all_cards['duplicate_of'].isnull()][['duplicate_of','code_str']].set_index('code_str')
    duplicates['duplicate_of_str'] = duplicates['duplicate_of'].to_frame().applymap(lambda x: "{:05.0f}".format(x))
    all_cards.loc[:,'unique_code'] = all_cards.loc[:, 'code_str']
    all_cards.loc[~all_cards['duplicate_of'].isna(), 'unique_code'] = all_cards.loc[~all_cards['duplicate_of'].isna(), 'duplicate_of'].astype(int).astype(str).apply(str.zfill, args=[5])
    
    import os
    import json

    PACKS_WITHOUT_PLAYER_CARDS = ['tsk', 'promotional', 'parallel', 'side_stories']

    all_packs = dict()

    with open(os.path.join('datafiles',  'cycles.json'), 'r') as f:
        cycles = json.load(f)
    with open(os.path.join('datafiles',  'packs.json'), 'r') as f:
        packs = json.load(f)

    # print(packs)


    for pack in packs:
        all_packs[pack.pop('code')] = pack

    # Export to file
    duplicates.to_pickle("datafiles/duplicates.pickle")
    all_cards.to_pickle("datafiles/all_cards.pickle")

    return [all_cards, duplicates, all_packs]
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
    
    #Transforms date_update in datetime
    all_decks_clean.loc[:,'time_date_update'] = all_decks_clean['date_update'].apply(lambda x: datetime.strptime(x[:10],'%Y-%m-%d'))
    

    logging.info('Cleaning decks...')
    for d in all_decks_clean['slots']:
#         logging.info('.',end='',flush=True)
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
    logging.info("\n Done")
    
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

def update_cards_repository():
    import os
    os.system('git -C ../arkhamdb-json-data pull')
    os.system('cp -a ../arkhamdb-json-data/pack/. datafiles/cards/')
    os.system('cp ../arkhamdb-json-data/cycles.json datafiles/')
    os.system('cp ../arkhamdb-json-data/packs.json datafiles/')

update_cards_repository()
read_decks_from_arkhamdb()


def convert_text_to_icons(text):
    import re

    rep = {
        '[eldersign]': '<span class="icon-eldersign" title="Elder Sign"></span>',
        '[elder_sign]': '<span class="icon-elder_sign" title="Elder Sign"></span>',
        '[cultist]' : '<span class="icon-cultist" title="Cultist"></span>',
        '[tablet]' : '<span class="icon-tablet" title="Tablet"></span>',
        '[elder_thing]' : '<span class="icon-elder_thing" title="Elder Thing"></span>',
        '[auto_fail]' : '<span class="icon-auto_fail" title="Auto Fail"></span>',
        '[fail]' : '<span class="icon-auto_fail" title="Auto Fail"></span>',
        '[skull]' : '<span class="icon-skull" title="Skull"></span>',
        '[reaction]' : '<span class="icon-reaction" title="Reaction"></span>',
        '[action]' : '<span class="icon-action" title="Action"></span>',
        '[lightning]' : '<span class="icon-lightning" title="Fast Action"></span>',
        '[fast]' : '<span class="icon-lightning" title="Fast Action"></span>',
        '[free]' : '<span class="icon-lightning" title="Fast Action"></span>',
        '[willpower]' : '<span class="icon-willpower" title="Willpower"></span>',
        '[intellect]' : '<span class="icon-intellect" title="Intellect"></span>',
        '[combat]' : '<span class="icon-combat" title="Combat"></span>',
        '[agility]' : '<span class="icon-agility" title="Agility"></span>',
        '[wild]' : '<span class="icon-wild" title="Any Skill"></span>',
        '[guardian]' : '<span class="icon-guardian" title="Guardian"></span>',
        '[survivor]' : '<span class="icon-survivor" title="Survivor"></span>',
        '[rogue]' : '<span class="icon-rogue" title="Rogue"></span>',
        '[seeker]' : '<span class="icon-seeker" title="Seeker"></span>',
        '[mystic]' : '<span class="icon-mystic" title="Mystic"></span>',
        '[neutral]' : '<span class="icon-neutral" title="Neutral">Neutral</span>',
        '[per_investigator]' : '<span class="icon-per_investigator" title="Per Investigator"></span>',
        '[bless]' : '<span class="icon-bless" title="Bless"></span>',
        '[curse]' : '<span class="icon-curse" title="Curse"></span>',
        '[frost]' : '<span class="icon-frost" title="frost"></span>',
        '[seal_a]' : '<span class="icon-seal_a" title="Seal A"></span>',
        '[seal_b]' : '<span class="icon-seal_b" title="Seal B"></span>',
        '[seal_c]' : '<span class="icon-seal_c" title="Seal C"></span>',
        '[seal_d]' : '<span class="icon-seal_d" title="Seal D"></span>',
        '[seal_e]' : '<span class="icon-seal_e" title="Seal E"></span>',
        '[[': '<b>',
        ']]': '</b>'
    }

    rep = dict((re.escape(k), v) for k, v in rep.items()) 
    pattern = re.compile("|".join(rep.keys()))
    text = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
    return text
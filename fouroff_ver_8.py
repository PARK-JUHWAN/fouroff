#!/usr/bin/env python3
"""
fouroff_ver_8.py - Ã¬ËœÂ¬Ã«Â°â€Ã«Â¥Â¸ wallet ÃªÂ³â€žÃ¬â€šÂ° (N+1, X+1 Ã­ÂÂ¬Ã­â€¢Â¨)
"""

import json
import sys
import calendar
import holidays
from collections import defaultdict
from ortools.sat.python import cp_model


# ========================================
# Z_RULES (64ÃªÂ°Å“ - All Soft Constraints)
# ========================================
Z_RULES = {
    0: ["X","D","E","N"],   1: ["X","E","N"],       2: ["N"],
    3: ["X","D","E","N"],   5: ["X","E","N"],       6: ["N"],
    7: ["X","D","E","N"],   10: ["N","X"],          12: ["D","E","N","X"],
    13: ["E","N","X"],      14: ["N"],              15: ["D","E","N","X"],
    21: ["X","E","N"],      22: ["N"],              23: ["X","D","E","N"],
    26: ["N","X"],          28: ["D","E","N","X"],  29: ["E","N","X"],
    30: ["N"],              31: ["D","E","N","X"],  42: ["X"],
    43: ["X"],              45: ["E","X"],          47: ["D","E","N","X"],
    48: ["D","E","N","X"],  49: ["E","N","X"],      50: ["N"],
    51: ["D","E","N","X"],  53: ["E","N","X"],      54: ["N"],
    55: ["D","E","N","X"],  58: ["N","X"],          60: ["D","E","N","X"],
    61: ["E","N","X"],      62: ["N"],              63: ["D","E","N","X"],
}

WEIGHT = {"D": 0, "E": 1, "N": 2, "X": 3}


# ========================================
# Validation Functions
# ========================================

def validate_input(data, parsed_data):
    """Ã¬Å¾â€¦Ã«Â Â¥ Ã«ÂÂ°Ã¬ÂÂ´Ã­â€žÂ° ÃªÂ²â‚¬Ã¬Â¦Â"""
    errors = []
    
    year = data['year']
    month = data['month']
    num_days = parsed_data['num_days']
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # past_3days ÃªÂ²â‚¬Ã¬Â¦Â
    for nurse_data in nurses_data:
        name = nurse_data['name']
        past = nurse_data.get('past_3days', [])
        
        if len(past) != 3:
            errors.append(f"{name}: past_3days must have exactly 3 elements")
        
        for i, duty in enumerate(past):
            if duty not in ['D', 'E', 'N', 'X']:
                errors.append(f"{name}: past_3days[{i}] invalid duty '{duty}'")
        
        # past_3days가 Z_RULES에 있는 패턴인지 확인
        if len(past) == 3 and all(d in ['D', 'E', 'N', 'X'] for d in past):
            z = 16 * WEIGHT[past[0]] + 4 * WEIGHT[past[1]] + 1 * WEIGHT[past[2]]
            if z not in Z_RULES:
                pattern = f"{past[0]}-{past[1]}-{past[2]}"
                errors.append(
                    f"{name}: past_3days pattern {pattern} (z={z}) is not allowed by Z_RULES. "
                    f"This pattern is forbidden and cannot occur."
                )
    
    # daily_wallet Ã­â€¢Â©ÃªÂ³â€ž ÃªÂ²â‚¬Ã¬Â¦Â
    daily_wallet = parsed_data['daily_wallet']
    for day, wallet in daily_wallet.items():
        total = sum(wallet.values())
        if total != nurse_count:
            errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    
    # Ã«â€šÂ Ã¬Â§Å“ Ã«Â²â€Ã¬Å“â€ž ÃªÂ²â‚¬Ã¬Â¦Â
    new_nurses = parsed_data['new_nurses']
    for name, info in new_nurses.items():
        start_day = info['start_day']
        if not (1 <= start_day <= num_days):
            errors.append(f"{name}: start_day ({start_day}) out of range")
    
    quit_nurses = parsed_data['quit_nurses']
    for name, info in quit_nurses.items():
        last_day = info['last_day']
        if not (1 <= last_day <= num_days):
            errors.append(f"{name}: last_day ({last_day}) out of range")
    
    # preference Ã¬Â¶Â©Ã«ÂÅ’ ÃªÂ²â‚¬Ã¬Â¦Â
    preferences = parsed_data['preferences']
    
    # daily_wallet Ã¬Â´Ë†ÃªÂ³Â¼ ÃªÂ²â‚¬Ã¬Â¦Â
    daily_pref_count = defaultdict(lambda: defaultdict(int))
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        for day_str, duty in schedule.items():
            day = int(day_str)
            daily_pref_count[day][duty] += 1
    
    for day, duty_counts in daily_pref_count.items():
        for duty, count in duty_counts.items():
            available = daily_wallet.get(day, {}).get(duty, 0)
            if count > available:
                errors.append(
                    f"Day {day} {duty}: {count} nurses want it but only {available} available"
                )
    
    return errors


def validate_result(result, parsed_data):
    """ÃªÂ²Â°ÃªÂ³Â¼ ÃªÂ²â‚¬Ã¬Â¦Â"""
    num_days = parsed_data['num_days']
    nurse_wallets = parsed_data['nurse_wallets']
    daily_wallet = parsed_data['daily_wallet']
    
    validation = {
        'daily_wallet_satisfied': True,
        'nurse_wallet_satisfied': True,
        'daily_violations': [],
        'nurse_violations': [],
        'nurse_duty_counts': {}
    }
    
    # Ã¬ÂÂ¼Ã«Â³â€ž ÃªÂ·Â¼Ã«Â¬Â´ Ã¬Â¹Â´Ã¬Å¡Â´Ã­Å Â¸
    for day in range(1, num_days + 1):
        day_count = defaultdict(int)
        
        for nurse, schedule in result.items():
            duty = schedule.get(str(day))
            if duty:
                day_count[duty] += 1
        
        for duty in ['D', 'E', 'N', 'X']:
            expected = daily_wallet[day][duty]
            actual = day_count[duty]
            
            if actual != expected:
                validation['daily_wallet_satisfied'] = False
                validation['daily_violations'].append(
                    f"Day {day} {duty}: expected {expected}, got {actual}"
                )
    
    # ÃªÂ°â€žÃ­ËœÂ¸Ã¬â€šÂ¬Ã«Â³â€ž ÃªÂ·Â¼Ã«Â¬Â´ Ã¬Â¹Â´Ã¬Å¡Â´Ã­Å Â¸
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # nurse_wallet Ã«Â§Å’Ã¬Â¡Â± Ã¬â€”Â¬Ã«Â¶â‚¬ (Ã‚Â±1 Ã­â€”Ë†Ã¬Å¡Â©)
        if nurse in nurse_wallets:
            for duty in ['D', 'E', 'N', 'X']:
                expected = nurse_wallets[nurse][duty]
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}Ã‚Â±1, got {actual}"
                    )
            
            # NÃ¬â€”Â Ã«Å’â‚¬Ã­â€¢Å“ Ã¬â€”â€žÃªÂ²Â©Ã­â€¢Å“ ÃªÂ²â‚¬Ã¬Â¦Â
            if 'N' in duty_count:
                expected_N = nurse_wallets[nurse]['N']
                actual_N = duty_count['N']
                remaining_N = expected_N - actual_N
                
                if remaining_N >= 2:
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse}: N Ã«Â¶â‚¬Ã¬Â¡Â± (Ã«â€šÂ¨Ã¬Ââ‚¬ N: {remaining_N}, Ã«ÂªÂ©Ã­â€˜Å“: <=1)"
                    )
    
    return validation


# ========================================
# Parse Input
# ========================================

def parse_input(input_json):
    """JSON Ã¬Å¾â€¦Ã«Â Â¥ Ã­Å’Å’Ã¬â€¹Â± Ã«Â°Â wallet ÃªÂ³â€žÃ¬â€šÂ°"""
    data = json.loads(input_json)
    
    year = data['year']
    month = data['month']
    num_days = calendar.monthrange(year, month)[1]
    
    # Ã«Å’â‚¬Ã­â€¢Å“Ã«Â¯Â¼ÃªÂµÂ­ ÃªÂ³ÂµÃ­Å“Â´Ã¬ÂÂ¼
    kr_holidays = holidays.KR(years=year)
    
    # daily_wallet Ã¬Æ’ÂÃ¬â€žÂ±
    daily_wallet_config = data.get('daily_wallet_config', {})
    weekday_wallet = daily_wallet_config.get('weekday', {})
    weekend_wallet = daily_wallet_config.get('weekend', {})
    
    daily_wallet = {}
    for day in range(1, num_days + 1):
        date = f"{year}-{month:02d}-{day:02d}"
        is_weekend = calendar.weekday(year, month, day) >= 5 or date in kr_holidays
        
        if is_weekend:
            daily_wallet[day] = dict(weekend_wallet)
        else:
            daily_wallet[day] = dict(weekday_wallet)
    
    # nurse_wallet ÃªÂ³â€žÃ¬â€šÂ°
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Keep Ã­Æ’â‚¬Ã¬Å¾â€¦Ã«Â³â€ž ÃªÂ°â€žÃ­ËœÂ¸Ã¬â€šÂ¬ Ã¬Ë†Ëœ Ã¬Â¹Â´Ã¬Å¡Â´Ã­Å Â¸
    all_nurses = []
    day_keep_nurses = []
    night_keep_nurses = []
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'DayÃ£â€¦Â¤':
            day_keep_nurses.append(name)
        elif keep_type == 'NightÃ£â€¦Â¤':
            night_keep_nurses.append(name)
        else:
            all_nurses.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all = len(all_nurses)
    
    print(f"[DEBUG] Keep Ã­Æ’â‚¬Ã¬Å¾â€¦ Ã«Â¶â€žÃ­ÂÂ¬: All={num_all}, DayÃ£â€¦Â¤={num_day_keep}, NightÃ£â€¦Â¤={num_night_keep}", file=sys.stderr)
    
    # Ã¬ÂÂ´ D, E, N, X ÃªÂ³â€žÃ¬â€šÂ°
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    print(f"[DEBUG] Ã­â€¢â€žÃ¬Å¡â€ Ã¬ÂÂ´Ã­â€¢Â©: D={total_D}, E={total_E}, N={total_N}, X={total_X}", file=sys.stderr)
    
    # nurse_wallets ÃªÂ³â€žÃ¬â€šÂ°
    nurse_wallets = {}
    
    # DayÃ£â€¦Â¤: DÃ«Â§Å’, E/N=0
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'D': num_days,
            'E': 0,
            'N': 0,
            'X': 2  # Ã¬â€”Â¬Ã¬Å“Â Ã«Â¶â€ž
        }
    
    # NightÃ£â€¦Â¤: N=15, D/E=0
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'D': 0,
            'E': 0,
            'N': 15,
            'X': num_days - 15 + 2  # Ã¬â€”Â¬Ã¬Å“Â Ã«Â¶â€ž
        }
    
    # All Ã­Æ’â‚¬Ã¬Å¾â€¦: ÃªÂ·Â Ã«â€œÂ± Ã«Â¶â€žÃ«Â°Â° + N+1, X+1 Ã¬â€”Â¬Ã¬Å“Â Ã«Â¶â€ž
    if num_all > 0:
        # DayÃ£â€¦Â¤Ã¬ÂÂ´ Ã¬â€šÂ¬Ã¬Å¡Â©Ã­â€¢ËœÃ«Å â€ Ã¬ÂÂ´ D
        day_keep_total_D = num_day_keep * num_days
        
        # NightÃ£â€¦Â¤Ã¬ÂÂ´ Ã¬â€šÂ¬Ã¬Å¡Â©Ã­â€¢ËœÃ«Å â€ Ã¬ÂÂ´ N
        night_keep_total_N = num_night_keep * 15
        
        # All Ã­Æ’â‚¬Ã¬Å¾â€¦Ã¬ÂÂ´ Ã¬â€šÂ¬Ã¬Å¡Â©Ã­â€¢Â´Ã¬â€¢Â¼ Ã­â€¢ËœÃ«Å â€ D, E, N, X
        all_total_D = total_D - day_keep_total_D
        all_total_E = total_E
        all_total_N = total_N - night_keep_total_N
        all_total_X = total_X
        
        print(f"[DEBUG] All Ã­Æ’â‚¬Ã¬Å¾â€¦Ã¬ÂÂ´ Ã¬â€šÂ¬Ã¬Å¡Â©Ã­â€¢Â´Ã¬â€¢Â¼ Ã­â€¢ËœÃ«Å â€ ÃªÂ·Â¼Ã«Â¬Â´: D={all_total_D}, E={all_total_E}, N={all_total_N}, X={all_total_X}", file=sys.stderr)
        
        # nurse_wallet_minÃ¬â€”ÂÃ¬â€žÅ“ min_N ÃªÂ°â‚¬Ã¬Â Â¸Ã¬ËœÂ¤ÃªÂ¸Â°
        nurse_wallet_min = data.get('nurse_wallet_min', {})
        min_N = nurse_wallet_min.get('N', 6)
        
        # ÃªÂ·Â Ã«â€œÂ± Ã«Â¶â€žÃ«Â°Â°
        per_nurse_D = all_total_D // num_all
        per_nurse_E = all_total_E // num_all
        per_nurse_N = min_N + 1  # N+1
        per_nurse_X = (all_total_X // num_all) + 1  # X+1
        
        # Ã«â€šËœÃ«Â¨Â¸Ã¬Â§â‚¬ Ã«Â¶â€žÃ«Â°Â°
        remainder_D = all_total_D % num_all
        remainder_E = all_total_E % num_all
        
        print(f"[DEBUG] ÃªÂ¸Â°Ã«Â³Â¸ Ã­â€¢Â Ã«â€¹Â¹: D={per_nurse_D}, E={per_nurse_E}, N={per_nurse_N}(min+1), X={per_nurse_X}(+1)", file=sys.stderr)
        
        for i, name in enumerate(all_nurses):
            d_count = per_nurse_D + (1 if i < remainder_D else 0)
            e_count = per_nurse_E + (1 if i < remainder_E else 0)
            n_count = per_nurse_N
            x_count = per_nurse_X
            
            nurse_wallets[name] = {
                'D': d_count,
                'E': e_count,
                'N': n_count,
                'X': x_count
            }

    
    print("[DEBUG] nurse_wallets ÃªÂ³â€žÃ¬â€šÂ° Ã¬â„¢â€žÃ«Â£Å’:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # Ã¬â€¹Â ÃªÂ·Å“/Ã­â€¡Â´Ã¬â€šÂ¬ ÃªÂ°â€žÃ­ËœÂ¸Ã¬â€šÂ¬ wallet Ã¬Â¡Â°Ã¬Â â€¢
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data['start_day']
        n_count = new_data['n_count']
        
        work_days = num_days - start_day + 1
        
        # Ã¬â€¹Â ÃªÂ·Å“: XÃ«Å â€ Ã¬Â¶Å“ÃªÂ·Â¼ Ã¬Â â€ž, NÃ¬Ââ‚¬ Ã¬Â§â‚¬Ã¬Â â€¢ÃªÂ°â€™
        nurse_wallets[name]['X'] = start_day - 1 + nurse_wallets[name]['X']
        nurse_wallets[name]['N'] = n_count
        
        # D, E Ã¬Å¾Â¬ÃªÂ³â€žÃ¬â€šÂ°
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        new_nurses[name] = {'start_day': start_day, 'n_count': n_count}
    
    quit_nurses = {}
    for quit_data in quit_nurses_list:
        name = quit_data['name']
        last_day = quit_data['last_day']
        n_count = quit_data['n_count']
        
        work_days = last_day
        
        # Ã­â€¡Â´Ã¬â€šÂ¬: XÃ«Å â€ Ã­â€¡Â´Ã¬â€šÂ¬ Ã­â€ºâ€ž, NÃ¬Ââ‚¬ Ã¬Â§â‚¬Ã¬Â â€¢ÃªÂ°â€™
        nurse_wallets[name]['X'] += (num_days - last_day)
        nurse_wallets[name]['N'] = n_count
        
        # D, E Ã¬Å¾Â¬ÃªÂ³â€žÃ¬â€šÂ°
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        quit_nurses[name] = {'last_day': last_day, 'n_count': n_count}
    
    # preferencesÃ¬â€”ÂÃ¬â€žÅ“ Ã¬Â°Â¨ÃªÂ°Â
    preferences = data.get('preferences', [])
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                if duty in nurse_wallets[name]:
                    nurse_wallets[name][duty] -= 1
    
    print("[DEBUG] Ã¬â€¹Â ÃªÂ·Å“/Ã­â€¡Â´Ã¬â€šÂ¬/Ã­ÂÂ¬Ã«Â§Â Ã«Â°ËœÃ¬ËœÂ Ã­â€ºâ€ž nurse_wallets:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # ÃªÂ²â‚¬Ã¬Â¦Â Ã¬Ë†ËœÃ­â€“â€°
    parsed_data = {
        'year': year,
        'month': month,
        'num_days': num_days,
        'daily_wallet': daily_wallet,
        'nurse_wallets': nurse_wallets,
        'new_nurses': new_nurses,
        'quit_nurses': quit_nurses,
        'preferences': preferences,
        'nurses_data': nurses_data
    }
    
    errors = validate_input(data, parsed_data)
    if errors:
        raise ValueError("Ã¬Å¾â€¦Ã«Â Â¥ ÃªÂ²â‚¬Ã¬Â¦Â Ã¬â€¹Â¤Ã­Å’Â¨:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return parsed_data


# ========================================
# CP-SAT Solver
# ========================================

def solve_cpsat(parsed_data):
    """CP-SATÃ«Â¡Å“ ÃªÂ·Â¼Ã«Â¬Â´Ã­â€˜Å“ Ã¬Æ’ÂÃ¬â€žÂ±"""
    year = parsed_data['year']
    month = parsed_data['month']
    num_days = parsed_data['num_days']
    daily_wallet = parsed_data['daily_wallet']
    nurse_wallets = parsed_data['nurse_wallets']
    new_nurses = parsed_data['new_nurses']
    quit_nurses = parsed_data['quit_nurses']
    preferences = parsed_data['preferences']
    nurses_data = parsed_data['nurses_data']
    
    print(f"[DEBUG] CP-SAT Ã¬â€¹Å“Ã¬Å¾â€˜: {year}Ã«â€¦â€ž {month}Ã¬â€ºâ€ ({num_days}Ã¬ÂÂ¼)", file=sys.stderr)
    
    nurses = list(nurse_wallets.keys())
    days = list(range(1, num_days + 1))
    duties = ['D', 'E', 'N', 'X']
    
    model = cp_model.CpModel()
    
    # Ã«Â³â‚¬Ã¬Ë†Ëœ Ã¬Æ’ÂÃ¬â€žÂ±
    x = {}
    for nurse in nurses:
        x[nurse] = {}
        for day in days:
            x[nurse][day] = {}
            for duty in duties:
                x[nurse][day][duty] = model.NewBoolVar(f'{nurse}_d{day}_{duty}')
    
    # Ã¬Â Å“Ã¬â€¢Â½ 1: Ã­â€¢ËœÃ«Â£Â¨Ã¬â€”Â Ã­â€¢ËœÃ«â€šËœÃ¬ÂËœ ÃªÂ·Â¼Ã«Â¬Â´Ã«Â§Å’
    for nurse in nurses:
        for day in days:
            model.Add(sum(x[nurse][day][duty] for duty in duties) == 1)
    
    # Ã¬Â Å“Ã¬â€¢Â½ 2: daily_wallet Ã«Â§Å’Ã¬Â¡Â±
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # Ã¬Â Å“Ã¬â€¢Â½ 3: nurse_wallet Ã«Â§Å’Ã¬Â¡Â± (Ã‚Â±1 Ã­â€”Ë†Ã¬Å¡Â©)
    for nurse in nurses:
        for duty in duties:
            target = nurse_wallets[nurse][duty]
            actual = sum(x[nurse][day][duty] for day in days)
            model.Add(actual >= target - 1)
            model.Add(actual <= target + 1)
    
    # Ã¬Â Å“Ã¬â€¢Â½ 4: Ã­ÂÂ¬Ã«Â§Â ÃªÂ·Â¼Ã«Â¬Â´ ÃªÂ³Â Ã¬Â â€¢
    pref_dict = {}
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        pref_dict[name] = schedule
    
    for nurse in nurses:
        if nurse in pref_dict:
            for day_str, duty in pref_dict[nurse].items():
                day = int(day_str)
                if day in days:
                    model.Add(x[nurse][day][duty] == 1)
    
    # Ã¬Â Å“Ã¬â€¢Â½ 5: Ã¬â€¹Â ÃªÂ·Å“ ÃªÂ°â€žÃ­ËœÂ¸Ã¬â€šÂ¬
    for name, data in new_nurses.items():
        start_day = data['start_day']
        # Ã¬Â¶Å“ÃªÂ·Â¼ Ã¬Â â€ž: X
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
        # Ã¬Â²Â«Ã«â€šÂ : D
        if start_day in days:
            model.Add(x[name][start_day]['D'] == 1)
    
    # Ã¬Â Å“Ã¬â€¢Â½ 6: Ã­â€¡Â´Ã¬â€šÂ¬ ÃªÂ°â€žÃ­ËœÂ¸Ã¬â€šÂ¬
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        # Ã­â€¡Â´Ã¬â€šÂ¬ Ã­â€ºâ€ž: X
        for day in range(last_day, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # Ã¬Â Å“Ã¬â€¢Â½ 7: Keep Ã­Æ’â‚¬Ã¬Å¾â€¦
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'DayÃ£â€¦Â¤':
            # E, N Ã¬Â Å“Ã¬â„¢Â¸
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'NightÃ£â€¦Â¤':
            # D, E Ã¬Â Å“Ã¬â„¢Â¸
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # 제약 8: zRule (모든 3일 연속 구간 검사)
    # z값 계산: 16*첫날 + 4*둘째날 + 1*셋째날
    # 구간: (-3,-2,-1), (-2,-1,1), (-1,1,2), (1,2,3), ..., (29,30,31)
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        # 모든 3일 연속 구간 생성
        all_windows = []
        all_windows.append((-3, -2, -1))
        all_windows.append((-2, -1, 1))
        all_windows.append((-1, 1, 2))
        for start in range(1, num_days - 1):
            all_windows.append((start, start + 1, start + 2))
        
        # 각 3일 구간에 zRule 적용
        for d1, d2, d3 in all_windows:
            # 다음 근무일 계산
            next_day = d3 + 1
            if next_day < 1 or next_day > num_days:
                continue
            
            # 각 날짜의 근무 타입
            duty_srcs = []
            for d in [d1, d2, d3]:
                if d < 0:
                    idx = d + 3  # -3→0, -2→1, -1→2
                    duty_srcs.append(('fixed', past_3days[idx]))
                else:
                    duty_srcs.append(('var', d))
            
            # Z_RULES의 모든 패턴 검사
            for z_val, allowed in Z_RULES.items():
                # z값 → 패턴 역산
                z_temp = z_val
                req = []
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d3
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d2
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d1
                req.reverse()  # [d1, d2, d3]
                
                # 매칭 확인
                match_vars = []
                fixed_ok = True
                
                for i in range(3):
                    if duty_srcs[i][0] == 'fixed':
                        if duty_srcs[i][1] != req[i]:
                            fixed_ok = False
                            break
                    else:
                        match_vars.append(x[nurse][duty_srcs[i][1]][req[i]])
                
                if not fixed_ok:
                    continue
                
                # 제약: 패턴 매칭 시 next_day는 allowed만
                if len(match_vars) == 0:
                    for duty in duties:
                        if duty not in allowed:
                            model.Add(x[nurse][next_day][duty] == 0)
                else:
                    match_all = model.NewBoolVar(f'z_{nurse}_{d1}_{d2}_{d3}_{z_val}')
                    model.Add(sum(match_vars) == len(match_vars)).OnlyEnforceIf(match_all)
                    model.Add(sum(match_vars) < len(match_vars)).OnlyEnforceIf(match_all.Not())
                    
                    for duty in duties:
                        if duty not in allowed:
                            model.Add(x[nurse][next_day][duty] == 0).OnlyEnforceIf(match_all)


    model.Minimize(0)
    
    # Ã¬â€ â€Ã«Â²â€ž Ã¬â€¹Â¤Ã­â€“â€°
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 8
    
    print("[DEBUG] CP-SAT Ã¬â€ â€Ã«Â²â€ž Ã¬â€¹Â¤Ã­â€“â€° Ã¬Â¤â€˜...", file=sys.stderr)
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"[DEBUG] Ã­â€¢Â´ÃªÂ²Â°Ã¬Â±â€¦ Ã«Â°Å“ÃªÂ²Â¬! (status={status})", file=sys.stderr)
        
        # ÃªÂ²Â°ÃªÂ³Â¼ Ã¬Â¶â€Ã¬Â¶Å“
        result = {}
        for nurse in nurses:
            result[nurse] = {}
            nurse_data = next(n for n in nurses_data if n['name'] == nurse)
            past_3days = nurse_data['past_3days']
            
            result[nurse]['-3'] = past_3days[0]
            result[nurse]['-2'] = past_3days[1]
            result[nurse]['-1'] = past_3days[2]
            
            for day in days:
                for duty in duties:
                    if solver.Value(x[nurse][day][duty]) == 1:
                        result[nurse][str(day)] = duty
                        break
        
        return result, solver
    
    else:
        error_msg = {
            cp_model.INFEASIBLE: "No feasible solution found",
            cp_model.MODEL_INVALID: "Model is invalid",
            cp_model.UNKNOWN: "Solver status unknown"
        }.get(status, f"Solver failed with status {status}")
        
        suggestions = [
            "Check daily_wallet sum equals nurse count",
            "Check nurse_wallet totals (with +1 buffer)",
            "Check preference conflicts",
            "Try relaxing constraints"
        ]
        
        raise RuntimeError(
            f"{error_msg}\n\nSuggestions:\n" + 
            "\n".join(f"  - {s}" for s in suggestions)
        )


# ========================================
# Main
# ========================================

def main():
    """Ã«Â©â€Ã¬ÂÂ¸ Ã¬â€¹Â¤Ã­â€“â€°"""
    if len(sys.argv) > 1:
        input_json = sys.argv[1]
    else:
        input_json = sys.stdin.read()
    
    try:
        # Ã­Å’Å’Ã¬â€¹Â± Ã«Â°Â ÃªÂ²â‚¬Ã¬Â¦Â
        parsed_data = parse_input(input_json)
        
        # Ã¬â€ â€Ã«Â²â€ž Ã¬â€¹Â¤Ã­â€“â€°
        result, solver = solve_cpsat(parsed_data)
        
        # ÃªÂ²Â°ÃªÂ³Â¼ ÃªÂ²â‚¬Ã¬Â¦Â
        validation = validate_result(result, parsed_data)
        
        output = {
            'status': 'success',
            'schedule': result,
            'nurse_wallets': parsed_data['nurse_wallets'],
            'validation': validation,
            'solver_stats': {
                'objective_value': solver.ObjectiveValue(),
                'wall_time': solver.WallTime(),
                'num_branches': solver.NumBranches()
            }
        }
        
        print(json.dumps(output, ensure_ascii=False, indent=2))
    
    except ValueError as e:
        print(json.dumps({
            'status': 'validation_error',
            'message': str(e)
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
    
    except RuntimeError as e:
        print(json.dumps({
            'status': 'solver_error',
            'message': str(e)
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
    
    except Exception as e:
        import traceback
        print(json.dumps({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

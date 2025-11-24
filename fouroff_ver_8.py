#!/usr/bin/env python3
"""
fouroff_ver_8.py - ÃƒÆ’Ã‚Â¬Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¥Ãƒâ€šÃ‚Â¸ wallet ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â° (N+1, X+1 ÃƒÆ’Ã‚Â­Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â¨)
"""

import json
import sys
import calendar
import holidays
from collections import defaultdict
from ortools.sat.python import cp_model


# ========================================
# Z_RULES (64ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°Ãƒâ€¦Ã¢â‚¬Å“ - All Soft Constraints)
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
    """ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â Ãƒâ€šÃ‚Â¥ ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â°ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â° ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â"""
    errors = []
    
    year = data['year']
    month = data['month']
    num_days = parsed_data['num_days']
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # past_3days ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
    for nurse_data in nurses_data:
        name = nurse_data['name']
        past = nurse_data.get('past_3days', [])
        
        if len(past) != 3:
            errors.append(f"{name}: past_3days must have exactly 3 elements")
        
        for i, duty in enumerate(past):
            if duty not in ['D', 'E', 'N', 'X']:
                errors.append(f"{name}: past_3days[{i}] invalid duty '{duty}'")
        
        # past_3daysÃªÂ°â‚¬ Z_RULESÃ¬â€”Â Ã¬Å¾Ë†Ã«Å â€ Ã­Å’Â¨Ã­â€žÂ´Ã¬ÂÂ¸Ã¬Â§â‚¬ Ã­â„¢â€¢Ã¬ÂÂ¸
        if len(past) == 3 and all(d in ['D', 'E', 'N', 'X'] for d in past):
            z = 16 * WEIGHT[past[0]] + 4 * WEIGHT[past[1]] + 1 * WEIGHT[past[2]]
            if z not in Z_RULES:
                pattern = f"{past[0]}-{past[1]}-{past[2]}"
                errors.append(
                    f"{name}: past_3days pattern {pattern} (z={z}) is not allowed by Z_RULES. "
                    f"This pattern is forbidden and cannot occur."
                )
    
    # daily_wallet ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
    daily_wallet = parsed_data['daily_wallet']
    for day, wallet in daily_wallet.items():
        total = sum(wallet.values())
        if total != nurse_count:
            errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    
    # ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â§Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
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
    
    # preference ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¶Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚ÂÃƒâ€¦Ã¢â‚¬â„¢ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
    preferences = parsed_data['preferences']
    
    # daily_wallet ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â´Ãƒâ€¹Ã¢â‚¬Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
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
    """ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â°ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â"""
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
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¬Ãƒâ€šÃ‚Â´ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¹Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â­Ãƒâ€¦Ã‚Â Ãƒâ€šÃ‚Â¸
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
    
    # ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â­Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¬Ãƒâ€šÃ‚Â´ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¹Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â­Ãƒâ€¦Ã‚Â Ãƒâ€šÃ‚Â¸
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # nurse_wallet ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¡Ãƒâ€šÃ‚Â± ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ (ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â±1 ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€¹Ã¢â‚¬Â ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â©)
        if nurse in nurse_wallets:
            for duty in ['D', 'E', 'N', 'X']:
                expected = nurse_wallets[nurse][duty]
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â±1, got {actual}"
                    )
            
            # NÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
            if 'N' in duty_count:
                expected_N = nurse_wallets[nurse]['N']
                actual_N = duty_count['N']
                remaining_N = expected_N - actual_N
                
                if remaining_N >= 2:
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse}: N ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¡Ãƒâ€šÃ‚Â± (ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¨ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ N: {remaining_N}, ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚ÂªÃƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‹Å“Ãƒâ€¦Ã¢â‚¬Å“: <=1)"
                    )
    
    return validation


# ========================================
# Parse Input
# ========================================

def parse_input(input_json):
    """JSON ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â Ãƒâ€šÃ‚Â¥ ÃƒÆ’Ã‚Â­Ãƒâ€¦Ã¢â‚¬â„¢Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â± ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â wallet ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â°"""
    data = json.loads(input_json)
    
    year = data['year']
    month = data['month']
    num_days = calendar.monthrange(year, month)[1]
    
    # ÃƒÆ’Ã‚Â«Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¯Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚ÂµÃƒâ€šÃ‚Â­ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³Ãƒâ€šÃ‚ÂµÃƒÆ’Ã‚Â­Ãƒâ€¦Ã¢â‚¬Å“Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¼
    kr_holidays = holidays.KR(years=year)
    
    # daily_wallet ÃƒÆ’Ã‚Â¬Ãƒâ€ Ã¢â‚¬â„¢Ãƒâ€šÃ‚ÂÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â±
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
    
    # nurse_wallet ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â°
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Keep ÃƒÆ’Ã‚Â­Ãƒâ€ Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â­Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ ÃƒÆ’Ã‚Â¬Ãƒâ€¹Ã¢â‚¬Â Ãƒâ€¹Ã…â€œ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¹Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â­Ãƒâ€¦Ã‚Â Ãƒâ€šÃ‚Â¸
    all_nurses = []
    day_keep_nurses = []
    night_keep_nurses = []
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'DayÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤':
            day_keep_nurses.append(name)
        elif keep_type == 'NightÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤':
            night_keep_nurses.append(name)
        else:
            all_nurses.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all = len(all_nurses)
    
    print(f"[DEBUG] Keep ÃƒÆ’Ã‚Â­Ãƒâ€ Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â­Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¬: All={num_all}, DayÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤={num_day_keep}, NightÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤={num_night_keep}", file=sys.stderr)
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ D, E, N, X ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â°
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    print(f"[DEBUG] ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â©: D={total_D}, E={total_E}, N={total_N}, X={total_X}", file=sys.stderr)
    
    # nurse_wallets ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â°
    nurse_wallets = {}
    
    # DayÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤: DÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€¦Ã¢â‚¬â„¢, E/N=0
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'D': num_days,
            'E': 0,
            'N': 0,
            'X': 2  # ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾
        }
    
    # NightÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤: N=15, D/E=0
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'D': 0,
            'E': 0,
            'N': 15,
            'X': num_days - 15 + 2  # ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾
        }
    
    # All ÃƒÆ’Ã‚Â­Ãƒâ€ Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦: ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒâ€šÃ‚Â± ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â° + N+1, X+1 ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾
    if num_all > 0:
        # DayÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«Ãƒâ€¦Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ D
        day_keep_total_D = num_day_keep * num_days
        
        # NightÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«Ãƒâ€¦Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ N
        night_keep_total_N = num_night_keep * 15
        
        # All ÃƒÆ’Ã‚Â­Ãƒâ€ Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«Ãƒâ€¦Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â D, E, N, X
        all_total_D = total_D - day_keep_total_D
        all_total_E = total_E
        all_total_N = total_N - night_keep_total_N
        all_total_X = total_X
        
        print(f"[DEBUG] All ÃƒÆ’Ã‚Â­Ãƒâ€ Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â´ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«Ãƒâ€¦Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¬Ãƒâ€šÃ‚Â´: D={all_total_D}, E={all_total_E}, N={all_total_N}, X={all_total_X}", file=sys.stderr)
        
        # nurse_wallet_minÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚ÂÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€¦Ã¢â‚¬Å“ min_N ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¤ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â°
        nurse_wallet_min = data.get('nurse_wallet_min', {})
        min_N = nurse_wallet_min.get('N', 6)
        
        # ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒâ€šÃ‚Â± ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â°
        per_nurse_D = all_total_D // num_all
        per_nurse_E = all_total_E // num_all
        per_nurse_N = min_N + 1  # N+1
        per_nurse_X = (all_total_X // num_all) + 1  # X+1
        
        # ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¨Ãƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â§ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â°
        remainder_D = all_total_D % num_all
        remainder_E = all_total_E % num_all
        
        print(f"[DEBUG] ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â°ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â³Ãƒâ€šÃ‚Â¸ ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â¹: D={per_nurse_D}, E={per_nurse_E}, N={per_nurse_N}(min+1), X={per_nurse_X}(+1)", file=sys.stderr)
        
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

    
    print("[DEBUG] nurse_wallets ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â° ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â£Ãƒâ€¦Ã¢â‚¬â„¢:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€¦Ã¢â‚¬Å“/ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â­Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ wallet ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data.get('start_day')
        n_count = new_data.get('n_count', 0)
        
        
        # start_dayê°€ Noneì´ë©´ ê±´ë„ˆë›°ê¸°
        if start_day is None:
            print(f"[WARNING] ì‹ ê·œ ê°„í˜¸ì‚¬ {name}ì˜ start_dayê°€ ì—†ì–´ì„œ ê±´ë„ˆëœë‹ˆë‹¤", file=sys.stderr)
            continue
        
        work_days = num_days - start_day + 1
        
        # ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€¦Ã¢â‚¬Å“: XÃƒÆ’Ã‚Â«Ãƒâ€¦Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¶Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾, NÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â§ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢
        nurse_wallets[name]['X'] = start_day - 1 + nurse_wallets[name]['X']
        nurse_wallets[name]['N'] = n_count
        
        # D, E ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â°
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        new_nurses[name] = {'start_day': start_day, 'n_count': n_count}
    
    quit_nurses = {}
    for quit_data in quit_nurses_list:
        name = quit_data['name']
        last_day = quit_data.get('last_day')
        n_count = quit_data.get('n_count', 0)
        
        
        # last_dayê°€ Noneì´ë©´ ê±´ë„ˆë›°ê¸°
        if last_day is None:
            print(f"[WARNING] í‡´ì‚¬ ê°„í˜¸ì‚¬ {name}ì˜ last_dayê°€ ì—†ì–´ì„œ ê±´ë„ˆëœë‹ˆë‹¤", file=sys.stderr)
            continue
        
        work_days = last_day
        
        # ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬: XÃƒÆ’Ã‚Â«Ãƒâ€¦Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂºÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾, NÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â§ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢
        nurse_wallets[name]['X'] += (num_days - last_day)
        nurse_wallets[name]['N'] = n_count
        
        # D, E ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â°
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        quit_nurses[name] = {'last_day': last_day, 'n_count': n_count}
    
    # preferencesÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚ÂÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â¨ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â
    preferences = data.get('preferences', [])
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                if duty in nurse_wallets[name]:
                    nurse_wallets[name][duty] -= 1
    
    print("[DEBUG] ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€¦Ã¢â‚¬Å“/ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬/ÃƒÆ’Ã‚Â­Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â¬Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂºÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ nurse_wallets:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€¹Ã¢â‚¬Â Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°
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
        raise ValueError("ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â Ãƒâ€šÃ‚Â¥ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â­Ãƒâ€¦Ã¢â‚¬â„¢Ãƒâ€šÃ‚Â¨:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return parsed_data


# ========================================
# CP-SAT Solver
# ========================================

def solve_cpsat(parsed_data):
    """CP-SATÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¡Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¬Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‹Å“Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚Â¬Ãƒâ€ Ã¢â‚¬â„¢Ãƒâ€šÃ‚ÂÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â±"""
    year = parsed_data['year']
    month = parsed_data['month']
    num_days = parsed_data['num_days']
    daily_wallet = parsed_data['daily_wallet']
    nurse_wallets = parsed_data['nurse_wallets']
    new_nurses = parsed_data['new_nurses']
    quit_nurses = parsed_data['quit_nurses']
    preferences = parsed_data['preferences']
    nurses_data = parsed_data['nurses_data']
    
    print(f"[DEBUG] CP-SAT ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‹Å“: {year}ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ {month}ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂºÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ({num_days}ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¼)", file=sys.stderr)
    
    nurses = list(nurse_wallets.keys())
    days = list(range(1, num_days + 1))
    duties = ['D', 'E', 'N', 'X']
    
    model = cp_model.CpModel()
    
    # ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â³ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¹Ã¢â‚¬Â Ãƒâ€¹Ã…â€œ ÃƒÆ’Ã‚Â¬Ãƒâ€ Ã¢â‚¬â„¢Ãƒâ€šÃ‚ÂÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â±
    x = {}
    for nurse in nurses:
        x[nurse] = {}
        for day in days:
            x[nurse][day] = {}
            for duty in duties:
                x[nurse][day][duty] = model.NewBoolVar(f'{nurse}_d{day}_{duty}')
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 1: ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â£Ãƒâ€šÃ‚Â¨ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€šÃ‚Â ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€¹Ã…â€œÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€¹Ã…â€œ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¬Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€¦Ã¢â‚¬â„¢
    for nurse in nurses:
        for day in days:
            model.Add(sum(x[nurse][day][duty] for duty in duties) == 1)
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 2: daily_wallet ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¡Ãƒâ€šÃ‚Â±
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 3: nurse_wallet ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¡Ãƒâ€šÃ‚Â± (ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â±1 ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂÃƒâ€¹Ã¢â‚¬Â ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â©)
    for nurse in nurses:
        for duty in duties:
            target = nurse_wallets[nurse][duty]
            actual = sum(x[nurse][day][duty] for day in days)
            model.Add(actual >= target - 1)
            model.Add(actual <= target + 1)
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 4: ÃƒÆ’Ã‚Â­Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â§Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â¬Ãƒâ€šÃ‚Â´ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢
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
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 5: ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€¦Ã¢â‚¬Å“ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â­Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬
    for name, data in new_nurses.items():
        start_day = data['start_day']
        # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¶Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â·Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾: X
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
        # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â«ÃƒÆ’Ã‚Â«ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â : D
        if start_day in days:
            model.Add(x[name][start_day]['D'] == 1)
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 6: ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â°ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ÃƒÆ’Ã‚Â­Ãƒâ€¹Ã…â€œÃƒâ€šÃ‚Â¸ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        # ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂºÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾: X
        for day in range(last_day, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â½ 7: Keep ÃƒÆ’Ã‚Â­Ãƒâ€ Ã¢â‚¬â„¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'DayÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤':
            # E, N ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢Ãƒâ€šÃ‚Â¸
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'NightÃƒÆ’Ã‚Â£ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦Ãƒâ€šÃ‚Â¤':
            # D, E ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢Ãƒâ€šÃ‚Â¸
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # Ã¬Â Å“Ã¬â€¢Â½ 8: zRule (Ã«ÂªÂ¨Ã«â€œÂ  3Ã¬ÂÂ¼ Ã¬â€”Â°Ã¬â€ Â ÃªÂµÂ¬ÃªÂ°â€ž ÃªÂ²â‚¬Ã¬â€šÂ¬)
    # zÃªÂ°â€™ ÃªÂ³â€žÃ¬â€šÂ°: 16*Ã¬Â²Â«Ã«â€šÂ  + 4*Ã«â€˜ËœÃ¬Â§Â¸Ã«â€šÂ  + 1*Ã¬â€¦â€¹Ã¬Â§Â¸Ã«â€šÂ 
    # ÃªÂµÂ¬ÃªÂ°â€ž: (-3,-2,-1), (-2,-1,1), (-1,1,2), (1,2,3), ..., (29,30,31)
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        # Ã«ÂªÂ¨Ã«â€œÂ  3Ã¬ÂÂ¼ Ã¬â€”Â°Ã¬â€ Â ÃªÂµÂ¬ÃªÂ°â€ž Ã¬Æ’ÂÃ¬â€žÂ±
        all_windows = []
        all_windows.append((-3, -2, -1))
        all_windows.append((-2, -1, 1))
        all_windows.append((-1, 1, 2))
        for start in range(1, num_days - 1):
            all_windows.append((start, start + 1, start + 2))
        
        # ÃªÂ°Â 3Ã¬ÂÂ¼ ÃªÂµÂ¬ÃªÂ°â€žÃ¬â€”Â zRule Ã¬Â ÂÃ¬Å¡Â©
        for d1, d2, d3 in all_windows:
            # Ã«â€¹Â¤Ã¬ÂÅ’ ÃªÂ·Â¼Ã«Â¬Â´Ã¬ÂÂ¼ ÃªÂ³â€žÃ¬â€šÂ°
            next_day = d3 + 1
            if next_day < 1 or next_day > num_days:
                continue
            
            # ÃªÂ°Â Ã«â€šÂ Ã¬Â§Å“Ã¬ÂËœ ÃªÂ·Â¼Ã«Â¬Â´ Ã­Æ’â‚¬Ã¬Å¾â€¦
            duty_srcs = []
            for d in [d1, d2, d3]:
                if d < 0:
                    idx = d + 3  # -3Ã¢â€ â€™0, -2Ã¢â€ â€™1, -1Ã¢â€ â€™2
                    duty_srcs.append(('fixed', past_3days[idx]))
                else:
                    duty_srcs.append(('var', d))
            
            # ëª¨ë“  ê°€ëŠ¥í•œ íŒ¨í„´(0~63) ê²€ì‚¬
            for z_val in range(64):
                # zê°’ â†’ íŒ¨í„´ ì—­ì‚°
                z_temp = z_val
                req = []
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d3
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d2
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d1
                req.reverse()  # [d1, d2, d3]
                
                # ë§¤ì¹­ í™•ì¸
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
                
                # Z_RULESì— ìžˆëŠ”ì§€ í™•ì¸
                if z_val not in Z_RULES:
                    # ê¸ˆì§€ëœ íŒ¨í„´: ì´ íŒ¨í„´ì´ ë°œìƒí•˜ì§€ ëª»í•˜ë„ë¡ ì œì•½
                    if len(match_vars) == 0:
                        # fixed íŒ¨í„´ì´ ê¸ˆì§€ëœ íŒ¨í„´ â†’ ìž…ë ¥ ê²€ì¦ ì˜¤ë¥˜
                        # (ì´ë¯¸ validate_inputì—ì„œ ê±¸ë ¤ì•¼ í•¨)
                        pass
                    else:
                        # ë³€ìˆ˜ í¬í•¨ â†’ ì´ íŒ¨í„´ì´ ë§¤ì¹­ë˜ì§€ ì•Šë„ë¡
                        match_all = model.NewBoolVar(f'forbidden_z_{nurse}_{d1}_{d2}_{d3}_{z_val}')
                        model.Add(sum(match_vars) == len(match_vars)).OnlyEnforceIf(match_all)
                        model.Add(sum(match_vars) < len(match_vars)).OnlyEnforceIf(match_all.Not())
                        
                        # ê¸ˆì§€ëœ íŒ¨í„´ ë°œìƒ ê¸ˆì§€
                        model.Add(match_all == 0)
                    continue
                
                # í—ˆìš©ëœ íŒ¨í„´: next_dayëŠ” allowedë§Œ
                allowed = Z_RULES[z_val]
                
                # ì œì•½: íŒ¨í„´ ë§¤ì¹­ ì‹œ next_dayëŠ” allowedë§Œ
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
    
    # ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0  # Render timeout ëŒ€ì‘
    solver.parameters.num_search_workers = 4  # ë©”ëª¨ë¦¬ ì ˆì•½
    solver.parameters.log_search_progress = False  # ë¡œê·¸ ìµœì†Œí™”
    
    # ì¡°ê¸° ì‹¤íŒ¨ ê°ì§€
    solver.parameters.cp_model_presolve = True
    solver.parameters.cp_model_probing_level = 2
    
    print("[DEBUG] CP-SAT ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â° ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¤ÃƒÂ¢Ã¢â€šÂ¬Ã‹Å“...", file=sys.stderr)
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"[DEBUG] ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢Ãƒâ€šÃ‚Â´ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â°ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â±ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€¦Ã¢â‚¬Å“ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â¬! (status={status})", file=sys.stderr)
        
        # ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â°ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¶ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¶Ãƒâ€¦Ã¢â‚¬Å“
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
            cp_model.INFEASIBLE: "No feasible solution found (ì œì•½ ì¡°ê±´ì„ ë§Œì¡±í•˜ëŠ” í•´ê°€ ì—†ìŒ)",
            cp_model.MODEL_INVALID: "Model is invalid (ëª¨ë¸ ì˜¤ë¥˜)",
            cp_model.UNKNOWN: "Solver status unknown (ì‹œê°„ ì´ˆê³¼ ë˜ëŠ” ì•Œ ìˆ˜ ì—†ëŠ” ì˜¤ë¥˜)"
        }.get(status, f"Solver failed with status {status}")
        
        # ìž…ë ¥ ê°’ ìš”ì•½
        total_nurses = len(nurses)
        weekday_staff = daily_wallet.get('weekday', {})
        weekend_staff = daily_wallet.get('weekend', {})
        
        input_summary = [
            f"Nurses: {total_nurses}ëª…",
            f"Weekday staff: D={weekday_staff.get('D',0)}, E={weekday_staff.get('E',0)}, N={weekday_staff.get('N',0)}",
            f"Weekend staff: D={weekend_staff.get('D',0)}, E={weekend_staff.get('E',0)}, N={weekend_staff.get('N',0)}",
            f"Total weekday required: {sum(weekday_staff.values())}",
            f"Total weekend required: {sum(weekend_staff.values())}",
        ]
        
        suggestions = [
            "ê°„í˜¸ì‚¬ ìˆ˜ê°€ ìš”êµ¬ ì¸ì›ë³´ë‹¤ ì ìœ¼ë©´ ë¶ˆê°€ëŠ¥í•©ë‹ˆë‹¤",
            "í‰ì¼/ì£¼ë§ ì¸ì› í•©ê³„ê°€ ì „ì²´ ê°„í˜¸ì‚¬ ìˆ˜ì™€ ê°™ì€ì§€ í™•ì¸í•˜ì„¸ìš”",
            "past_3daysê°€ ê¸ˆì§€ëœ íŒ¨í„´(N-D-N, D-N-D ë“±)ì´ë©´ ë‹¤ìŒë‚  ì œì•½ ìœ„ë°° ê°€ëŠ¥",
            "nurse_walletì˜ ìµœì†Œ N ê°œìˆ˜ê°€ ë„ˆë¬´ ë§Žìœ¼ë©´ ë¶ˆê°€ëŠ¥í•©ë‹ˆë‹¤",
            "í¬ë§ ê·¼ë¬´(preferences)ê°€ ë„ˆë¬´ ë§Žìœ¼ë©´ ì¶©ëŒ ê°€ëŠ¥ì„± ë†’ìŒ",
        ]
        
        raise RuntimeError(
            f"{error_msg}\n\nìž…ë ¥ ìš”ì•½:\n" + 
            "\n".join(f"  {s}" for s in input_summary) +
            "\n\nê¶Œìž¥ ì¡°ì¹˜:\n" + 
            "\n".join(f"  - {s}" for s in suggestions)
        )


# ========================================
# Main
# ========================================

def main():
    """ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â©ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â¸ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°"""
    if len(sys.argv) > 1:
        input_json = sys.argv[1]
    else:
        input_json = sys.stdin.read()
    
    try:
        # ÃƒÆ’Ã‚Â­Ãƒâ€¦Ã¢â‚¬â„¢Ãƒâ€¦Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â± ÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â°Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
        parsed_data = parse_input(input_json)
        
        # ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÆ’Ã‚Â«Ãƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ÃƒÆ’Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã‚Â­ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°
        result, solver = solve_cpsat(parsed_data)
        
        # ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²Ãƒâ€šÃ‚Â°ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â³Ãƒâ€šÃ‚Â¼ ÃƒÆ’Ã‚ÂªÃƒâ€šÃ‚Â²ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¬Ãƒâ€šÃ‚Â¦Ãƒâ€šÃ‚Â
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

#!/usr/bin/env python3
"""
fouroff_ver_8.py - Nurse Schedule Generator with CP-SAT Solver
WALLET REDESIGN: nurse_wallet = {N, X} only, D/E auto-distributed by daily_wallet
"""

import json
import sys
import math
import calendar
import holidays
import random
from collections import defaultdict
from ortools.sat.python import cp_model


# ========================================
# Z_RULES (64 entries - All Soft Constraints)
# Pattern format: previous 3 days -> allowed duties for next day
# z value = 16*day1 + 4*day2 + 1*day3 (D=0, E=1, N=2, X=3)
# Patterns NOT in Z_RULES are forbidden
# ========================================
Z_RULES = {
    0: ["X","D","E","N"],   # D-D-D / fixed
    1: ["X","E","N"],       # D-D-E / fixed
    2: ["N"],               # D-D-N / fixed
    3: ["X","D","E","N"],   # D-D-X / fixed
    # 4: D-E-D (forbidden)
    5: ["X","E","N"],       # D-E-E / fixed
    6: ["N"],               # D-E-N / fixed
    7: ["X","D","E","N"],   # D-E-X / fixed
    # 8: D-N-D (forbidden)
    # 9: D-N-E (forbidden)
    10: ["N","X"],          # D-N-N / fixed
    # 11: D-N-X (pending)
    12: ["D","E","N","X"],  # D-X-D / fixed
    13: ["E","N","X"],      # D-X-E / fixed
    14: ["N"],              # D-X-N / fixed
    15: ["D","E","N","X"],  # D-X-X / fixed
    # 16: E-D-D (forbidden)
    # 17: E-D-E (forbidden)
    # 18: E-D-N (forbidden)
    # 19: E-D-X (forbidden)
    # 20: E-E-D (forbidden)
    21: ["X","E","N"],      # E-E-E / fixed
    22: ["N"],              # E-E-N / fixed
    23: ["X","D","E","N"],  # E-E-X / fixed
    # 24: E-N-D (forbidden)
    # 25: E-N-E (forbidden)
    26: ["N","X"],          # E-N-N / fixed
    # 27: E-N-X (pending)
    28: ["D","E","N","X"],  # E-X-D / fixed
    29: ["E","N","X"],      # E-X-E / fixed
    30: ["N"],              # E-X-N / fixed
    31: ["D","E","N","X"],  # E-X-X / fixed
    # 32: N-D-D (forbidden)
    # 33: N-D-E (forbidden)
    # 34: N-D-N (forbidden)
    # 35: N-D-X (forbidden)
    # 36: N-E-D (forbidden)
    # 37: N-E-E (forbidden)
    # 38: N-E-N (forbidden)
    # 39: N-E-X (forbidden)
    # 40: N-N-D (forbidden)
    # 41: N-N-E (forbidden)
    42: ["X"],              # N-N-N / fixed
    43: ["X"],              # N-N-X / fixed
    # 44: N-X-D (forbidden)
    45: ["E","X"],          # N-X-E / fixed
    # 46: N-X-N (forbidden)
    47: ["D","E","N","X"],  # N-X-X / fixed
    48: ["D","E","N","X"],  # X-D-D / fixed
    49: ["E","N","X"],      # X-D-E / fixed
    50: ["N"],              # X-D-N / fixed
    51: ["D","E","N","X"],  # X-D-X / fixed
    # 52: X-E-D (forbidden)
    53: ["E","N","X"],      # X-E-E / fixed
    54: ["N"],              # X-E-N / fixed
    55: ["D","E","N","X"],  # X-E-X / fixed
    # 56: X-N-D (forbidden)
    # 57: X-N-E (forbidden)
    58: ["N","X"],          # X-N-N / fixed
    # 59: X-N-X (pending)
    60: ["D","E","N","X"],  # X-X-D / fixed
    61: ["E","N","X"],      # X-X-E / fixed
    62: ["N"],              # X-X-N / fixed
    63: ["D","E","N","X"],  # X-X-X / fixed
}

WEIGHT = {"D": 0, "E": 1, "N": 2, "X": 3}

def calculate_auto_x(work_days, num_days, total_weekends_holidays, forced_x):
    """
    Calculate X wallet for new/quit nurses.
    
    Args:
        work_days: Number of days nurse actually works
        num_days: Total days in month
        total_weekends_holidays: Weekends + holidays count in month
        forced_x: Days outside work period (auto X)
    
    Returns:
        int: Total X count (forced + work_period)
    """
    if work_days <= 0 or num_days <= 0:
        return forced_x
    
    work_ratio = work_days / num_days
    work_period_x = int(total_weekends_holidays * work_ratio)  # floor
    
    return forced_x + work_period_x


# Night샤 법적 기준 N 개수 (전국 공통)
NIGHT_KEEP_N_COUNT = 15


# ========================================
# Validation Functions
# ========================================

def validate_input(data, parsed_data):
    """Validate input data"""
    errors = []
    
    year = data['year']
    month = data['month']
    num_days = parsed_data['num_days']
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Validate past_3days
    for nurse_data in nurses_data:
        name = nurse_data['name']
        past = nurse_data.get('past_3days', [])
        
        if len(past) != 3:
            errors.append(f"{name}: past_3days must have exactly 3 elements")
        
        for i, duty in enumerate(past):
            if duty not in ['D', 'E', 'N', 'X']:
                errors.append(f"{name}: past_3days[{i}] invalid duty '{duty}'")
        
        # Check if past_3days pattern is in Z_RULES
        if len(past) == 3 and all(d in ['D', 'E', 'N', 'X'] for d in past):
            z = 16 * WEIGHT[past[0]] + 4 * WEIGHT[past[1]] + 1 * WEIGHT[past[2]]
            if z not in Z_RULES:
                pattern = f"{past[0]}-{past[1]}-{past[2]}"
                errors.append(
                    f"{name}: past_3days pattern {pattern} (z={z}) is not allowed by Z_RULES. "
                    f"This pattern is forbidden and cannot occur."
                )

    # Validate daily_wallet sum
    daily_wallet = parsed_data['daily_wallet']
    for day, wallet in daily_wallet.items():
        total = sum(wallet.values())
        if total != nurse_count:
            errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    
    # Validate date range for new nurses
    new_nurses = parsed_data['new_nurses']
    for name, info in new_nurses.items():
        start_day = info['start_day']
        if not (1 <= start_day <= num_days):
            errors.append(f"{name}: start_day ({start_day}) out of range")
    
    # Validate date range for quit nurses
    quit_nurses = parsed_data['quit_nurses']
    for name, info in quit_nurses.items():
        last_day = info['last_day']
        if not (1 <= last_day <= num_days):
            errors.append(f"{name}: last_day ({last_day}) out of range")
    
    # Validate preference conflicts
    preferences = parsed_data['preferences']
    
    # Check daily_wallet overflow
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
    """Validate generated schedule result"""
    num_days = parsed_data['num_days']
    nurse_wallets = parsed_data['nurse_wallets']
    daily_wallet = parsed_data['daily_wallet']
    low_grade_nurses = parsed_data.get('low_grade_nurses', [])
    
    validation = {
        'daily_wallet_satisfied': True,
        'nurse_wallet_satisfied': True,
        'low_grade_satisfied': True,
        'daily_violations': [],
        'nurse_violations': [],
        'low_grade_violations': [],
        'nurse_duty_counts': {}
    }
    
    # Check daily duty counts
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
    
    # Check nurse duty counts (N, X only for new wallet structure)
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # Check nurse_wallet satisfaction (N, X only, allow +/-1)
        if nurse in nurse_wallets:
            for duty in ['N', 'X']:
                expected = nurse_wallets[nurse].get(duty, 0)
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}+/-1, got {actual}"
                    )
            
            # Check remaining N count
            if 'N' in duty_count:
                expected_N = nurse_wallets[nurse].get('N', 0)
                actual_N = duty_count['N']
                remaining_N = expected_N - actual_N
                
                if remaining_N >= 2:
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse}: N shortage (remaining N: {remaining_N}, target: <=1)"
                    )
    
    # Check Low Grade Rule
    if len(low_grade_nurses) >= 2:
        for day in range(1, num_days + 1):
            for duty in ['D', 'E', 'N']:
                count = sum(1 for nurse in low_grade_nurses 
                           if result.get(nurse, {}).get(str(day)) == duty)
                if count > 1:
                    validation['low_grade_satisfied'] = False
                    validation['low_grade_violations'].append(
                        f"Day {day} {duty}: Low Grade {count} assigned (max 1)"
                    )
    
    return validation


# ========================================
# Parse Input
# ========================================

def parse_input(input_json):
    """Parse JSON input and calculate wallets (N, X only)"""
    data = json.loads(input_json)
    
    year = data['year']
    month = data['month']
    num_days = calendar.monthrange(year, month)[1]
    
    # Korean holidays
    kr_holidays = holidays.KR(years=year)
    
    # Generate daily_wallet
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
    
    # Validate daily_wallet is not empty
    if not weekday_wallet or not all(k in weekday_wallet for k in ['D', 'E', 'N', 'X']):
        raise ValueError(
            f"daily_wallet_config.weekday is missing or incomplete.\n"
            f"  Received: {weekday_wallet}\n"
            f"  Expected: {{'D': int, 'E': int, 'N': int, 'X': int}}\n"
            f"  Full config: {daily_wallet_config}"
        )
    
    if not weekend_wallet or not all(k in weekend_wallet for k in ['D', 'E', 'N', 'X']):
        raise ValueError(
            f"daily_wallet_config.weekend is missing or incomplete.\n"
            f"  Received: {weekend_wallet}\n"
            f"  Expected: {{'D': int, 'E': int, 'N': int, 'X': int}}\n"
            f"  Full config: {daily_wallet_config}"
        )
    
    # Calculate nurse_wallet (N, X only)
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Get new/quit nurse lists
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    new_nurse_names = set(n['name'] for n in new_nurses_list)
    quit_nurse_names = set(q['name'] for q in quit_nurses_list)
    
    # Extract max_consecutive_work early
    max_consecutive_work = data.get('max_consecutive_work', 6)
    if not (1 <= max_consecutive_work <= 10):
        raise ValueError(f"max_consecutive_work must be 1~10, got {max_consecutive_work}")
    
    # Calculate weekday/weekend counts
    weekdays = 0
    weekends = 0
    
    for day in range(1, num_days + 1):
        date = f"{year}-{month:02d}-{day:02d}"
        is_weekend = calendar.weekday(year, month, day) >= 5
        is_holiday = date in kr_holidays
        
        if is_weekend or is_holiday:
            weekends += 1
        else:
            weekdays += 1
    
    # Classify nurses by keep_type (excluding new/quit for All count)
    all_nurses_existing = []  # All 기존
    day_keep_nurses = []      # DK 기존
    night_keep_nurses = []    # NK 기존
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        # Skip new/quit nurses from type classification
        if name in new_nurse_names or name in quit_nurse_names:
            continue
        
        if keep_type == 'DayFixed':
            day_keep_nurses.append(name)
        elif keep_type == 'NightFixed':
            night_keep_nurses.append(name)
        else:
            all_nurses_existing.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all_existing = len(all_nurses_existing)
    num_new = len(new_nurse_names)
    num_quit = len(quit_nurse_names)
    
    # Calculate monthly totals
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    # ========================================
    # (A-1-1) Special 휴가 차감
    # ========================================
    for nurse_data in nurses_data:
        special_days = nurse_data.get('special_days', 0)
        if special_days > 0:
            total_X -= special_days
    
    # ========================================
    # (A-2) NK/DK/All 신규퇴사 N, X 차감
    # ========================================
    
    # NK 기존
    total_N -= num_night_keep * NIGHT_KEEP_N_COUNT
    total_X -= num_night_keep * (num_days - NIGHT_KEEP_N_COUNT)
    
    # DK 기존 (N=0이므로 X만)
    total_X -= num_day_keep * weekends
    
    # NK 신규/퇴사
    for n in new_nurses_list:
        nurse_data = next((nd for nd in nurses_data if nd['name'] == n['name']), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        if keep_type == 'NightFixed':
            total_N -= n.get('n_count', 0)
            total_X -= n.get('x_count', num_days - n.get('n_count', 0))
    
    for q in quit_nurses_list:
        nurse_data = next((nd for nd in nurses_data if nd['name'] == q['name']), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        if keep_type == 'NightFixed':
            total_N -= q.get('n_count', 0)
            total_X -= q.get('x_count', num_days - q.get('n_count', 0))
    
    # DK 신규/퇴사
    for n in new_nurses_list:
        nurse_data = next((nd for nd in nurses_data if nd['name'] == n['name']), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        if keep_type == 'DayFixed':
            start_day = n.get('start_day', 1)
            work_weekends = sum(1 for day in range(start_day, num_days + 1)
                               if calendar.weekday(year, month, day) >= 5 or 
                               f"{year}-{month:02d}-{day:02d}" in kr_holidays)
            total_X -= (start_day - 1) + work_weekends
    
    for q in quit_nurses_list:
        nurse_data = next((nd for nd in nurses_data if nd['name'] == q['name']), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        if keep_type == 'DayFixed':
            last_day = q.get('last_day', num_days)
            work_weekends = sum(1 for day in range(1, last_day + 1)
                               if calendar.weekday(year, month, day) >= 5 or 
                               f"{year}-{month:02d}-{day:02d}" in kr_holidays)
            total_X -= work_weekends + (num_days - last_day)
    
    # All 신규/퇴사 (X, N만)
    for n in new_nurses_list:
        nurse_data = next((nd for nd in nurses_data if nd['name'] == n['name']), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        if keep_type == 'All':
            total_N -= n.get('n_count', 0)
            total_X -= n.get('x_count', 0)
    
    for q in quit_nurses_list:
        nurse_data = next((nd for nd in nurses_data if nd['name'] == q['name']), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        if keep_type == 'All':
            total_N -= q.get('n_count', 0)
            total_X -= q.get('x_count', 0)
    
    # ê²°ê³¼: all_available_N, all_available_X
    all_available_N = total_N
    all_available_X = total_X
    
    # ========================================
    # (A-3) All 기존 N, X 계산
    # ========================================
    nurse_wallets = {}
    
    if num_all_existing > 0:
        # Get user input min_N
        nurse_wallet_min = data.get('nurse_wallet_min', {})
        user_min_N = nurse_wallet_min.get('N', 6)
        
        # Calculate max_min_N (floor division)
        max_min_N = all_available_N // num_all_existing
        
        # Calculate min_min_N (lower bound)
        min_min_N = math.ceil(all_available_N / num_all_existing) - 1
        
        # Validate user_min_N - Lower bound check
        if user_min_N < min_min_N:
            raise ValueError(
                f"min_N={user_min_N}은(는) 너무 낮습니다.\n"
                f"  이유: All 타입 간호사 {num_all_existing}명이 N {all_available_N}개를 소화하려면\n"
                f"        최소 {min_min_N}개씩 근무해야 합니다.\n"
                f"  최소 min_N: {min_min_N}\n"
                f"  해결방법:\n"
                f"    1. min_N을 {min_min_N} 이상으로 올리기\n"
                f"    2. 일별 N 인원 줄이기\n"
                f"    3. Night샤 인원 늘리기"
            )
        
        # Validate user_min_N - Upper bound check
        if user_min_N > max_min_N:
            raise ValueError(
                f"min_N={user_min_N}은(는) 불가능합니다.\n"
                f"  이유: All 타입 간호사 {num_all_existing}명이 사용할 수 있는 N은 총 {all_available_N}개입니다.\n"
                f"  최대 min_N: {max_min_N} (= {all_available_N} // {num_all_existing})\n"
                f"  해결방법:\n"
                f"    1. min_N을 {max_min_N} 이하로 낮추기\n"
                f"    2. 일별 N 인원 늘리기\n"
                f"    3. Night샤 인원 줄이기"
            )
        
        per_nurse_N = user_min_N
        per_nurse_X = all_available_X // num_all_existing
        remainder_X = all_available_X % num_all_existing
        
        # (B-1) + (B-2) All 기존 wallet 생성 (버퍼 포함)
        for i, name in enumerate(all_nurses_existing):
            x_count = per_nurse_X + (1 if i < remainder_X else 0)
            
            nurse_wallets[name] = {
                'N': per_nurse_N + 1,  # N+1 버퍼
                'X': x_count + 1       # X+1 버퍼
            }
    
    # ========================================
    # (B-1) DK 기존 wallet
    # ========================================
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'N': 0,
            'X': weekends
        }
    
    # ========================================
    # (B-1) NK 기존 wallet
    # ========================================
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'N': NIGHT_KEEP_N_COUNT,
            'X': num_days - NIGHT_KEEP_N_COUNT
        }
    
    # ========================================
    # (B-1) 신규/퇴사 wallet
    # ========================================
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data.get('start_day')
        n_count = new_data.get('n_count', 0)
        x_count = new_data.get('x_count', 0)
        
        if start_day is None:
            print(f"[WARNING] New nurse {name} has no start_day, skipping", file=sys.stderr)
            continue
        
        nurse_data = next((n for n in nurses_data if n['name'] == name), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        de_preference = nurse_data.get('de_preference', '=') if nurse_data else '='
        
        if keep_type == 'DayFixed':
            work_weekends = sum(1 for day in range(start_day, num_days + 1)
                               if calendar.weekday(year, month, day) >= 5 or 
                               f"{year}-{month:02d}-{day:02d}" in kr_holidays)
            nurse_wallets[name] = {
                'N': 0,
                'X': (start_day - 1) + work_weekends
            }
        elif keep_type == 'NightFixed':
            # NK 신규: N manual, X auto
            work_days = num_days - start_day + 1
            forced_x = start_day - 1
            auto_x = calculate_auto_x(work_days, num_days, weekends, forced_x)
            
            nurse_wallets[name] = {
                'N': n_count,
                'X': auto_x
            }
        else:
            # All 신규: N manual, X auto
            work_days = num_days - start_day + 1
            forced_x = start_day - 1
            auto_x = calculate_auto_x(work_days, num_days, weekends, forced_x)
            
            nurse_wallets[name] = {
                'N': n_count,
                'X': auto_x
            }
        
        new_nurses[name] = {
            'start_day': start_day, 
            'n_count': n_count, 
            'keep_type': keep_type,
            'de_preference': de_preference
        }
    
    quit_nurses = {}
    for quit_data in quit_nurses_list:
        name = quit_data['name']
        last_day = quit_data.get('last_day')
        n_count = quit_data.get('n_count', 0)
        x_count = quit_data.get('x_count', 0)
        
        if last_day is None:
            print(f"[WARNING] Quit nurse {name} has no last_day, skipping", file=sys.stderr)
            continue
        
        nurse_data = next((n for n in nurses_data if n['name'] == name), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        de_preference = nurse_data.get('de_preference', '=') if nurse_data else '='
        
        if keep_type == 'DayFixed':
            work_weekends = sum(1 for day in range(1, last_day + 1)
                               if calendar.weekday(year, month, day) >= 5 or 
                               f"{year}-{month:02d}-{day:02d}" in kr_holidays)
            nurse_wallets[name] = {
                'N': 0,
                'X': work_weekends + (num_days - last_day)
            }
        elif keep_type == 'NightFixed':
            # NK 퇴사: N manual, X auto
            work_days = last_day
            forced_x = num_days - last_day
            auto_x = calculate_auto_x(work_days, num_days, weekends, forced_x)
            
            nurse_wallets[name] = {
                'N': n_count,
                'X': auto_x
            }
        else:
            # All 퇴사: N manual, X auto
            work_days = last_day
            forced_x = num_days - last_day
            auto_x = calculate_auto_x(work_days, num_days, weekends, forced_x)
            
            nurse_wallets[name] = {
                'N': n_count,
                'X': auto_x
            }
        
        quit_nurses[name] = {
            'last_day': last_day, 
            'n_count': n_count, 
            'keep_type': keep_type,
            'de_preference': de_preference
        }
    
    # ========================================
    # (B-3) DE 선호도 저장 (All 타입만)
    # ========================================
    de_preferences = {}
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        de_pref = nurse_data.get('de_preference', '=')
        
        if keep_type == 'All':
            de_preferences[name] = de_pref
    
    # Special days 저장
    special_days_dict = {}
    for nurse_data in nurses_data:
        name = nurse_data['name']
        special_days = nurse_data.get('special_days', 0)
        if special_days > 0:
            special_days_dict[name] = special_days
            # Special days를 해당 간호사 X에 추가
            if name in nurse_wallets:
                nurse_wallets[name]['X'] += special_days
    
    # Deduct preferences from wallets (N, X만)
    # Note: 퇴사자의 last_day 이후, 신규의 start_day 이전은 이미 강제 X이므로 차감 제외
    preferences = data.get('preferences', [])
    special_exempt = {name: count for name, count in special_days_dict.items()} ###
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                day = int(day_str)
                
                # 퇴사자: last_day 이후는 이미 강제 X이므로 차감 제외
                if name in quit_nurses:
                    last_day = quit_nurses[name]['last_day']
                    if day > last_day:
                        continue
                
                # 신규: start_day 이전은 이미 강제 X이므로 차감 제외
                if name in new_nurses:
                    start_day = new_nurses[name]['start_day']
                    if day < start_day:
                        continue
                
                # if duty in nurse_wallets[name]:
                #     nurse_wallets[name][duty] -= 1
                ###
                if duty in nurse_wallets[name]:
                    # X이고 special_days 면제 남아있으면 차감하지 않음
                    if duty == 'X' and special_exempt.get(name, 0) > 0:
                        special_exempt[name] -= 1
                        continue  # Skip deduction
                    nurse_wallets[name][duty] -= 1
                ###     
    
    # Extract Low Grade nurses
    low_grade_nurses = []
    for nurse_data in nurses_data:
        name = nurse_data['name']
        is_low_grade = nurse_data.get('is_low_grade', False)
        if is_low_grade:
            low_grade_nurses.append(name)
    
    # Calculate max_low_grade
    max_low_grade = min(
        weekday_wallet['D'],
        weekday_wallet['E'],
        weekday_wallet['N'],
        weekend_wallet['D'],
        weekend_wallet['E'],
        weekend_wallet['N'],
    )
    
    # Validate Low Grade count
    if len(low_grade_nurses) > max_low_grade:
        raise ValueError(
            f"Low Grade exceeds limit: {len(low_grade_nurses)} > max {max_low_grade}\n"
            f"  Low Grade nurses: {low_grade_nurses}\n"
            f"  Reduce Low Grade count or increase D/E/N staff per day"
        )
    
    # Extract min_N for Constraint 3
    nurse_wallet_min_global = data.get('nurse_wallet_min', {})
    min_N_value = nurse_wallet_min_global.get('N', 6)
    
    # Execute validation
    parsed_data = {
        'year': year,
        'month': month,
        'num_days': num_days,
        'daily_wallet': daily_wallet,
        'nurse_wallets': nurse_wallets,
        'new_nurses': new_nurses,
        'quit_nurses': quit_nurses,
        'preferences': preferences,
        'nurses_data': nurses_data,
        'low_grade_nurses': low_grade_nurses,
        'max_low_grade': max_low_grade,
        'max_consecutive_work': max_consecutive_work,
        'min_N': min_N_value,
        'de_preferences': de_preferences,
        'special_days': special_days_dict
    }
    
    errors = validate_input(data, parsed_data)
    if errors:
        raise ValueError("Input validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return parsed_data


# ========================================
# CP-SAT Solver
# ========================================

def solve_cpsat(parsed_data):
    """Generate schedule using CP-SAT solver"""
    year = parsed_data['year']
    month = parsed_data['month']
    num_days = parsed_data['num_days']
    daily_wallet = parsed_data['daily_wallet']
    nurse_wallets = parsed_data['nurse_wallets']
    new_nurses = parsed_data['new_nurses']
    quit_nurses = parsed_data['quit_nurses']
    preferences = parsed_data['preferences']
    nurses_data = parsed_data['nurses_data']
    de_preferences = parsed_data.get('de_preferences', {})
    special_days_dict = parsed_data.get('special_days', {}) ###
    
    nurses = list(nurse_wallets.keys())
    days = list(range(1, num_days + 1))
    duties = ['D', 'E', 'N', 'X']
    
    model = cp_model.CpModel()
    
    # Create variables
    x = {}
    for nurse in nurses:
        x[nurse] = {}
        for day in days:
            x[nurse][day] = {}
            for duty in duties:
                x[nurse][day][duty] = model.NewBoolVar(f'{nurse}_d{day}_{duty}')
    
    # Constraint 1: One duty per day per nurse
    for nurse in nurses:
        for day in days:
            model.Add(sum(x[nurse][day][duty] for duty in duties) == 1)
    
    # Constraint 2: Satisfy daily_wallet (DENX 모두)
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # Constraint 3: Satisfy nurse_wallet (N, X만 검증)
    min_N = parsed_data.get('min_N', 6)
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        keep_type = nurse_data.get('keep_type', 'All')
        
        is_new = nurse in new_nurses
        is_quit = nurse in quit_nurses
        
        # N 제약
        target_N = nurse_wallets[nurse].get('N', 0)
        actual_N = sum(x[nurse][day]['N'] for day in days)
        
        if keep_type == 'NightFixed':
            if is_new or is_quit:
                # NK 신규/퇴사: 입력값 기준 ±1
                model.Add(actual_N >= target_N - 1)
                model.Add(actual_N <= target_N + 1)
            else:
                # NK 기존: 정확히 15
                model.Add(actual_N == NIGHT_KEEP_N_COUNT)
        elif keep_type == 'DayFixed':
            # DK: N=0
            model.Add(actual_N == 0)
        else:
            # All 타입
            if is_new or is_quit:
                # All 신규/퇴사: 입력값 기준 ±1
                model.Add(actual_N >= target_N - 1)
                model.Add(actual_N <= target_N + 1)
            else:
                # All 기존: min_N 이상, target+1 이하
                model.Add(actual_N >= min_N)
                model.Add(actual_N <= target_N + 1)
        
        # X 제약 (상한만)
        target_X = nurse_wallets[nurse].get('X', 0)
        actual_X = sum(x[nurse][day]['X'] for day in days)
        model.Add(actual_X <= target_X + 1)
        ### if nurse in special_days_dict:
        model.Add(actual_X >= target_X - 1) ###
    
    # Constraint 4: Fix preference duties
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
    
    # Constraint 5: New nurses - X before start_day
    for name, data in new_nurses.items():
        start_day = data['start_day']
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # Constraint 6: Quit nurses - X after last_day
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        for day in range(last_day + 1, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # Constraint 7: Keep type restrictions
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if name not in nurse_wallets:
            continue
        
        if keep_type == 'DayFixed':
            # DK: E=0, N=0
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'NightFixed':
            # NK: D=0, E=0
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # Constraint 8: zRule
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        all_windows = []
        all_windows.append((-3, -2, -1))
        all_windows.append((-2, -1, 1))
        all_windows.append((-1, 1, 2))
        for start in range(1, num_days - 1):
            all_windows.append((start, start + 1, start + 2))
        
        for d1, d2, d3 in all_windows:
            if d3 == -1:
                next_day = 1
            elif d3 < 1:
                continue
            else:
                next_day = d3 + 1
            
            if next_day < 1 or next_day > num_days:
                continue
            
            # Skip zRule for new nurses' pre-start windows
            if nurse in new_nurses:
                start_day = new_nurses[nurse]['start_day']
                window_days = [d for d in [d1, d2, d3, next_day] if d > 0]
                if any(d < start_day for d in window_days):
                    continue
            
            # Skip zRule for quit nurses' post-last windows
            if nurse in quit_nurses:
                last_day = quit_nurses[nurse]['last_day']
                window_days = [d for d in [d1, d2, d3, next_day] if d > 0]
                if any(d > last_day for d in window_days):
                    continue
            
            duty_srcs = []
            for d in [d1, d2, d3]:
                if d < 0:
                    idx = d + 3
                    duty_srcs.append(('fixed', past_3days[idx]))
                else:
                    duty_srcs.append(('var', d))
            
            for z_val in range(64):
                z_temp = z_val
                req = []
                req.append(["D", "E", "N", "X"][z_temp % 4])
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])
                req.reverse()
                
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
                
                if z_val not in Z_RULES:
                    if len(match_vars) > 0:
                        match_all = model.NewBoolVar(f'forbidden_z_{nurse}_{d1}_{d2}_{d3}_{z_val}')
                        model.Add(sum(match_vars) == len(match_vars)).OnlyEnforceIf(match_all)
                        model.Add(sum(match_vars) < len(match_vars)).OnlyEnforceIf(match_all.Not())
                        model.Add(match_all == 0)
                    continue
                
                allowed = Z_RULES[z_val]
                
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

    # Constraint 9: Low Grade Rule
    low_grade_nurses = parsed_data.get('low_grade_nurses', [])
    
    if len(low_grade_nurses) >= 2:
        for day in days:
            for duty in ['D', 'E', 'N']:
                model.Add(sum(x[nurse][day][duty] for nurse in low_grade_nurses if nurse in nurse_wallets) <= 1)

    # Constraint 10: Maximum Consecutive Work Days
    max_consecutive_work = parsed_data.get('max_consecutive_work', 6)
    window_size = max_consecutive_work + 1
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        work_start = 1
        work_end = num_days
        
        if nurse in new_nurses:
            work_start = new_nurses[nurse]['start_day']
        if nurse in quit_nurses:
            work_end = quit_nurses[nurse]['last_day']
        
        for win_start in range(work_start, work_end - window_size + 2):
            win_end = win_start + window_size - 1
            
            if win_end > work_end:
                break
            
            model.Add(
                sum(x[nurse][day]['X'] for day in range(win_start, win_end + 1)) >= 1
            )
        
        if nurse not in new_nurses:
            past_x_count = sum(1 for d in past_3days if d == 'X')
            
            if past_x_count == 0:
                remaining_window = window_size - 3
                if remaining_window > 0 and remaining_window <= num_days:
                    model.Add(
                        sum(x[nurse][day]['X'] for day in range(1, remaining_window + 1)) >= 1
                    )

    # ========================================
    # Objective: DE 선호도 (Soft)
    # ========================================
    objective_terms = []
    
    for nurse in nurses:
        if nurse not in de_preferences:
            continue
        
        nurse_data = next((n for n in nurses_data if n['name'] == nurse), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        
        if keep_type != 'All':
            continue
        
        pref = de_preferences[nurse]
        
        # 근무 기간 결정
        work_start = 1
        work_end = num_days
        if nurse in new_nurses:
            work_start = new_nurses[nurse]['start_day']
        if nurse in quit_nurses:
            work_end = quit_nurses[nurse]['last_day']
        
        work_days = list(range(work_start, work_end + 1))
        
        D_count = sum(x[nurse][day]['D'] for day in work_days)
        E_count = sum(x[nurse][day]['E'] for day in work_days)
        
        if pref == 'D':
            # D 선호: D-E 최대화
            objective_terms.append(D_count - E_count)
        elif pref == 'E':
            # E 선호: E-D 최대화
            objective_terms.append(E_count - D_count)
        # '=' 인 경우: 목표에 추가 안 함 (자연스럽게 균등 분배)
    
    if objective_terms:
        model.Maximize(sum(objective_terms))
    else:
        model.Minimize(0)
    
    # Run solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_search_workers = 4
    solver.parameters.log_search_progress = False
    solver.parameters.random_seed = random.randint(1, 100000)
    solver.parameters.cp_model_presolve = True
    solver.parameters.cp_model_probing_level = 2
    
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
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
            cp_model.INFEASIBLE: "No feasible solution found (constraints cannot be satisfied)",
            cp_model.MODEL_INVALID: "Model is invalid (model error)",
            cp_model.UNKNOWN: "Solver status unknown (timeout or unknown error)"
        }.get(status, f"Solver failed with status {status}")
        
        total_nurses = len(nurses)
        day1_wallet = daily_wallet.get(1, {})
        
        weekend_wallet = {}
        for d in range(1, num_days + 1):
            if calendar.weekday(year, month, d) >= 5:
                weekend_wallet = daily_wallet.get(d, {})
                break
        
        input_summary = [
            f"Nurses: {total_nurses}",
            f"Day1 wallet: D={day1_wallet.get('D',0)}, E={day1_wallet.get('E',0)}, N={day1_wallet.get('N',0)}, X={day1_wallet.get('X',0)}",
            f"Weekend wallet: D={weekend_wallet.get('D',0)}, E={weekend_wallet.get('E',0)}, N={weekend_wallet.get('N',0)}, X={weekend_wallet.get('X',0)}",
        ]
        
        suggestions = [
            "Check if nurse count matches daily_wallet sum",
            "Check past_3days patterns for forbidden sequences",
            "Verify min_N is within valid range",
            "Check for preference conflicts",
        ]
        
        raise RuntimeError(
            f"{error_msg}\n\nInput summary:\n" + 
            "\n".join(f"  {s}" for s in input_summary) +
            "\n\nSuggestions:\n" + 
            "\n".join(f"  - {s}" for s in suggestions)
        )


# ========================================
# Main
# ========================================

def main():
    """Main execution"""
    if len(sys.argv) > 1:
        input_json = sys.argv[1]
    else:
        input_json = sys.stdin.read()
    
    try:
        parsed_data = parse_input(input_json)
        result, solver = solve_cpsat(parsed_data)
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
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    except RuntimeError as e:
        print(json.dumps({
            'status': 'solver_error',
            'message': str(e)
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    except Exception as e:
        import traceback
        print(json.dumps({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()

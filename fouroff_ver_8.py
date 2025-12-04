#!/usr/bin/env python3
"""
fouroff_ver_8.py - Nurse Schedule Generator with CP-SAT Solver
Simulation wallet calculation (N+1, X+1 buffer allowed)
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

    ### delete
    # # Validate daily_wallet sum
    daily_wallet = parsed_data['daily_wallet']
    # for day, wallet in daily_wallet.items():
    #     total = sum(wallet.values())
    #     if total != nurse_count:
    #         errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    ### delete
    
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
    
    # Check nurse duty counts
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # Check nurse_wallet satisfaction (allow +/-1)
        if nurse in nurse_wallets:
            for duty in ['D', 'E', 'N', 'X']:
                expected = nurse_wallets[nurse][duty]
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}+/-1, got {actual}"
                    )
            
            # Check remaining N count
            if 'N' in duty_count:
                expected_N = nurse_wallets[nurse]['N']
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
    """Parse JSON input and calculate wallets"""
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
    
    # Debug: Log actual input values
    ### print(f"[INPUT] daily_wallet_config: {daily_wallet_config}", file=sys.stderr)
    ### print(f"[INPUT] weekday_wallet: {weekday_wallet}", file=sys.stderr)
    ### print(f"[INPUT] weekend_wallet: {weekend_wallet}", file=sys.stderr)
    
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
    
    # Calculate nurse_wallet
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Get new/quit nurse lists
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    ### print(f"[DEBUG] quit_nurses_list: {quit_nurses_list}", file=sys.stderr)
    new_nurse_names = set(n['name'] for n in new_nurses_list)
    quit_nurse_names = set(q['name'] for q in quit_nurses_list)

    ### change
    for new_data in new_nurses_list:
        start_day = new_data.get('start_day')
        if start_day is None:
            continue
        for day in range(1, start_day):  # 1 ~ start_day-1
            if day in daily_wallet:
                daily_wallet[day]['X'] -= 1
    # 퇴사자: last_day 이후 = X 강제
    for quit_data in quit_nurses_list:
        last_day = quit_data.get('last_day')
        if last_day is None:
            continue
        for day in range(last_day + 1, num_days + 1):  # last_day+1 ~ num_days
            if day in daily_wallet:
                daily_wallet[day]['X'] -= 1
    ### change
    
    # Extract max_consecutive_work early (needed for new/quit wallet calculation)
    max_consecutive_work = data.get('max_consecutive_work', 6)
    if not (1 <= max_consecutive_work <= 10):
        raise ValueError(f"max_consecutive_work must be 1~10, got {max_consecutive_work}")
    
    # Classify nurses by keep_type (excluding new/quit for All count)
    all_nurses = []
    day_keep_nurses = []
    night_keep_nurses = []
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        # Skip new/quit nurses from type classification (they're handled separately)
        if name in new_nurse_names or name in quit_nurse_names:
            continue
        
        if keep_type == 'DayFixed':
            day_keep_nurses.append(name)
        elif keep_type == 'NightFixed':
            night_keep_nurses.append(name)
        else:
            all_nurses.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all = len(all_nurses)
    num_new = len(new_nurse_names)
    num_quit = len(quit_nurse_names)
    
    # Calculate monthly D, E, N, X totals
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    # Initialize nurse_wallets
    nurse_wallets = {}
    
    # Calculate weekday/weekend counts for Day샤
    kr_holidays = holidays.KR(years=year)
    weekdays = 0
    weekends = 0
    
    for day in range(1, num_days + 1):
        date = f"{year}-{month:02d}-{day:02d}"
        is_weekend = calendar.weekday(year, month, day) >= 5  # Saturday(5), Sunday(6)
        is_holiday = date in kr_holidays
        
        if is_weekend or is_holiday:
            weekends += 1
        else:
            weekdays += 1
    
    # DayFixed nurses: D=weekdays, E=0, N=0, X=weekends
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'D': weekdays,
            'E': 0,
            'N': 0,
            'X': weekends
        }
    
    # NightFixed nurses: D=0, E=0, N=15 (legal standard), X=remainder
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'D': 0,
            'E': 0,
            'N': NIGHT_KEEP_N_COUNT,  # 15 (legal standard)
            'X': num_days - NIGHT_KEEP_N_COUNT
        }
    
    # Calculate N consumed by Night샤 and new/quit nurses
    night_keep_total_N = num_night_keep * NIGHT_KEEP_N_COUNT
    new_quit_total_N = sum(n['n_count'] for n in new_nurses_list) + sum(q['n_count'] for q in quit_nurses_list)
    consumed_N = night_keep_total_N + new_quit_total_N
    
    # Calculate available N for All type nurses
    all_available_N = total_N - consumed_N

    ### plus
    # ========================================
    # Calculate D, E consumed by new/quit nurses (BEFORE All wallet calculation)
    # ========================================
    quit_new_total_D = 0
    quit_new_total_E = 0
    quit_new_total_X = 0  # X 차감용 추가
    day_keep_new_quit_D = 0  # DayKeep 신규/퇴사의 D
    
    for q in quit_nurses_list:
        qname = q['name']
        # Get keep_type for this quit nurse
        nurse_data = next((n for n in nurses_data if n['name'] == qname), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        
        work_days = q['last_day']
        n_count = q.get('n_count', 0)
        
        if keep_type == 'NightFixed':
            # NightKeep: D=0, E=0
            pass
        elif keep_type == 'DayFixed':
            # DayKeep: D=work_weekdays, E=0
            work_weekdays = 0
            for day in range(1, q['last_day'] + 1):
                date = f"{year}-{month:02d}-{day:02d}"
                is_weekend = calendar.weekday(year, month, day) >= 5
                is_holiday = date in kr_holidays
                if not (is_weekend or is_holiday):
                    work_weekdays += 1
            day_keep_new_quit_D += work_weekdays
        else:
            # All type: D, E, X 균등 분배
            x_work = (work_days - 1) // max_consecutive_work
            x_total = (num_days - q['last_day']) + x_work
            remaining = work_days - n_count - x_work
            quit_new_total_D += remaining // 2
            quit_new_total_E += remaining - (remaining // 2)
            quit_new_total_X += x_total
    
    for n in new_nurses_list:
        nname = n['name']
        # Get keep_type for this new nurse
        nurse_data = next((nd for nd in nurses_data if nd['name'] == nname), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        
        work_days = num_days - n['start_day'] + 1
        n_count = n.get('n_count', 0)
        
        if keep_type == 'NightFixed':
            # NightKeep: D=0, E=0
            pass
        elif keep_type == 'DayFixed':
            # DayKeep: D=work_weekdays, E=0
            work_weekdays = 0
            for day in range(n['start_day'], num_days + 1):
                date = f"{year}-{month:02d}-{day:02d}"
                is_weekend = calendar.weekday(year, month, day) >= 5
                is_holiday = date in kr_holidays
                if not (is_weekend or is_holiday):
                    work_weekdays += 1
            day_keep_new_quit_D += work_weekdays
        else:
            # All type: D, E, X 균등 분배
            x_work = (work_days - 1) // max_consecutive_work
            x_total = (n['start_day'] - 1) + x_work
            remaining = work_days - n_count - x_work
            quit_new_total_D += remaining // 2
            quit_new_total_E += remaining - (remaining // 2)
            quit_new_total_X += x_total
    ### plus
    
    # All type nurses: Dynamic min_N calculation
    if num_all > 0:
        # Calculate D usage by DayFixed nurses
        day_keep_total_D = num_day_keep * weekdays
        
        # Calculate remaining D, E, X for All type nurses
        ### all_total_D = total_D - day_keep_total_D
        ### all_total_E = total_E  # All E goes to All type
        all_total_D = total_D - day_keep_total_D - quit_new_total_D - day_keep_new_quit_D ### plus
        all_total_E = total_E - quit_new_total_E ### plus
        all_total_X = total_X - quit_new_total_X  # X 차감 적용
        
        # Get user input min_N
        nurse_wallet_min = data.get('nurse_wallet_min', {})
        user_min_N = nurse_wallet_min.get('N', 6)
        
        # Calculate max_min_N (floor division)
        max_min_N = all_available_N // num_all
        
        # Validate user_min_N
        
        # Calculate min_min_N (lower bound) - NEW
        # min_min_N = ceil(all_available_N / num_all) - 1
        # This ensures: (min_N + 1) * num_all >= all_available_N
        min_min_N = math.ceil(all_available_N / num_all) - 1
        
        # Validate user_min_N - Lower bound check (NEW)
        if user_min_N < min_min_N:
            raise ValueError(
                f"min_N={user_min_N}은(는) 너무 낮습니다.\n"
                f"  이유: All 타입 간호사 {num_all}명이 N {all_available_N}개를 소화하려면\n"
                f"        최소 {min_min_N}개씩 근무해야 합니다.\n"
                f"  현재 설정으로 wallet 합계: {num_all} × {user_min_N + 1} = {num_all * (user_min_N + 1)}개\n"
                f"  필요한 N: {all_available_N}개\n"
                f"  최소 min_N: {min_min_N}\n"
                f"  해결방법:\n"
                f"    1. min_N을 {min_min_N} 이상으로 올리기\n"
                f"    2. 일별 N 인원 줄이기\n"
                f"    3. Night샤 인원 늘리기"
            )
        
        # Validate user_min_N - Upper bound check (기존)
        if user_min_N > max_min_N:
            raise ValueError(
                f"min_N={user_min_N}은(는) 불가능합니다.\n"
                f"  이유: All 타입 간호사 {num_all}명이 사용할 수 있는 N은 총 {all_available_N}개입니다.\n"
                f"  최대 min_N: {max_min_N} (= {all_available_N} // {num_all})\n"
                f"  Night샤({num_night_keep}명)가 {night_keep_total_N}개, 신규/퇴사가 {new_quit_total_N}개를 이미 사용 중입니다.\n"
                f"  해결방법:\n"
                f"    1. min_N을 {max_min_N} 이하로 낮추기\n"
                f"    2. 일별 N 인원 늘리기\n"
                f"    3. Night샤 인원 줄이기"
            )
        # Use dynamic min_N if keep types exist, else use user input
        if num_night_keep > 0 or num_day_keep > 0 or num_new > 0 or num_quit > 0:
            # Dynamic mode: use max_min_N (버퍼 제거됨)
            per_nurse_N = max_min_N
        else:
            # Simple mode: use user input (버퍼 제거됨)
            per_nurse_N = user_min_N
        
        # Equal distribution for D, E, X
        per_nurse_D = all_total_D // num_all
        per_nurse_E = all_total_E // num_all
        ### per_nurse_X = (all_total_X // num_all) + 1  # X+1 buffer

        ### change
        if num_quit > 0 or num_new > 0:
            per_nurse_X = all_total_X // num_all  # No buffer
        else:
            per_nurse_X = (all_total_X // num_all) + 1  # X+1 buffer
        ### change

        # Remainder distribution
        remainder_D = all_total_D % num_all
        remainder_E = all_total_E % num_all

        ### delete
        # # Check buffer
        # total_allocated_N = num_all * per_nurse_N
        # buffer_N = total_allocated_N - all_available_N
        
        # if buffer_N < 0:
        #     raise ValueError(
        #         f"N 버퍼 부족: {buffer_N}\n"
        #         f"  All 타입 {num_all}명 × wallet N {per_nurse_N}개 = {total_allocated_N}개\n"
        #         f"  사용 가능한 N: {all_available_N}개\n"
        #         f"  부족: {-buffer_N}개"
        #     )
        ### delete
        
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

    
    # Debug disabled
    # print("[DEBUG] nurse_wallets calculation complete:", file=sys.stderr)
    # for name, wallet in nurse_wallets.items():
    #     print(f"  {name}: {wallet}", file=sys.stderr)
    
    # Adjust wallets for new/quit nurses
    # Note: new_nurses_list and quit_nurses_list already declared above
    
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data.get('start_day')
        n_count = new_data.get('n_count', 0)
        
        # Skip if start_day is None
        if start_day is None:
            print(f"[WARNING] New nurse {name} has no start_day, skipping", file=sys.stderr)
            continue
        
        work_days = num_days - start_day + 1
        
        # Get keep_type for new nurse
        nurse_data = next((n for n in nurses_data if n['name'] == name), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        
        # Initialize wallet based on keep_type
        if keep_type == 'DayFixed':
            # Day샤: D=weekdays in work period, E=0, N=0, X=days before start + weekends in work period
            # Calculate weekdays/weekends in work period
            work_weekdays = 0
            work_weekends = 0
            for day in range(start_day, num_days + 1):
                date = f"{year}-{month:02d}-{day:02d}"
                is_weekend = calendar.weekday(year, month, day) >= 5
                is_holiday = date in kr_holidays
                if is_weekend or is_holiday:
                    work_weekends += 1
                else:
                    work_weekdays += 1
            
            nurse_wallets[name] = {
                'D': work_weekdays,
                'E': 0,
                'N': 0,
                'X': (start_day - 1) + work_weekends
            }
        
        elif keep_type == 'NightFixed':
            # Night샤 신규: 입력받은 n_count 사용 (15 아님!)
            nurse_wallets[name] = {
                'D': 0,
                'E': 0,
                'N': n_count,  # User input, NOT 15
                'X': num_days - n_count
            }
        
        else:
            # All type: X before start + X_work, specified N count, D/E distributed
            # BUG FIX: Constraint 10 requires X within work period
            X_work = (work_days - 1) // max_consecutive_work  # Required X within work period
            X_total = (start_day - 1) + X_work
            
            # Recalculate D, E (accounting for X_work)
            remaining = work_days - n_count - X_work
            D_count = remaining // 2
            E_count = remaining - D_count
            
            nurse_wallets[name] = {
                'D': D_count,
                'E': E_count,
                'N': n_count,
                'X': X_total
            }
        
        new_nurses[name] = {'start_day': start_day, 'n_count': n_count, 'keep_type': keep_type}
    
    quit_nurses = {}
    for quit_data in quit_nurses_list:
        name = quit_data['name']
        last_day = quit_data.get('last_day')
        n_count = quit_data.get('n_count', 0)
        
        # Skip if last_day is None
        if last_day is None:
            print(f"[WARNING] Quit nurse {name} has no last_day, skipping", file=sys.stderr)
            continue
        
        work_days = last_day
        
        # Get keep_type for quit nurse
        nurse_data = next((n for n in nurses_data if n['name'] == name), None)
        keep_type = nurse_data.get('keep_type', 'All') if nurse_data else 'All'
        
        # Initialize wallet based on keep_type
        if keep_type == 'DayFixed':
            # Day샤: D=weekdays in work period, E=0, N=0, X=weekends in work period + days after last
            work_weekdays = 0
            work_weekends = 0
            for day in range(1, last_day + 1):
                date = f"{year}-{month:02d}-{day:02d}"
                is_weekend = calendar.weekday(year, month, day) >= 5
                is_holiday = date in kr_holidays
                if is_weekend or is_holiday:
                    work_weekends += 1
                else:
                    work_weekdays += 1
            
            nurse_wallets[name] = {
                'D': work_weekdays,
                'E': 0,
                'N': 0,
                'X': work_weekends + (num_days - last_day)
            }
        
        elif keep_type == 'NightFixed':
            # Night샤 퇴사: 입력받은 n_count 사용
            nurse_wallets[name] = {
                'D': 0,
                'E': 0,
                'N': n_count,
                'X': num_days - n_count
            }
        
        else:
            # All type: X after last day + X_work, specified N count, D/E distributed
            # BUG FIX: Constraint 10 requires X within work period
            X_work = (work_days - 1) // max_consecutive_work  # Required X within work period
            X_total = (num_days - last_day) + X_work
            
            # Recalculate D, E (accounting for X_work)
            remaining = work_days - n_count - X_work
            D_count = remaining // 2
            E_count = remaining - D_count
            
            nurse_wallets[name] = {
                'D': D_count,
                'E': E_count,
                'N': n_count,
                'X': X_total
            }
        quit_nurses[name] = {'last_day': last_day, 'n_count': n_count, 'keep_type': keep_type}

    ### debug
    # print(f"[D1] num_all={num_all}", file=sys.stderr, flush=True)
    # print(f"[D2] num_quit={num_quit}", file=sys.stderr, flush=True)
    # print(f"[D3] total_N={total_N}", file=sys.stderr, flush=True)
    # print(f"[D4] all_available_N={all_available_N}", file=sys.stderr, flush=True)
    # print(f"[D5] per_nurse_N={per_nurse_N}", file=sys.stderr, flush=True)
    # print(f"[D6] max_consecutive_work={max_consecutive_work}", file=sys.stderr, flush=True)
    # for qn in quit_nurses_list:
    #     qname = qn['name']
    #     w = nurse_wallets.get(qname, {})
    #     print(f"[D7] quit_in_wallet={qname in nurse_wallets}", file=sys.stderr, flush=True)
    #     print(f"[D8] q_D={w.get('D','?')}", file=sys.stderr, flush=True)
    #     print(f"[D9] q_E={w.get('E','?')}", file=sys.stderr, flush=True)
    #     print(f"[D10] q_N={w.get('N','?')}", file=sys.stderr, flush=True)
    #     print(f"[D11] q_X={w.get('X','?')}", file=sys.stderr, flush=True)
    # print(f"[D12] wallet_count={len(nurse_wallets)}", file=sys.stderr, flush=True)
    # print(f"[D13] N_sum={sum(w['N'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    # print(f"[D14] quit_nurses_keys={list(quit_nurses.keys())}", file=sys.stderr, flush=True)
    # print(f"[D15] D_sum={sum(w['D'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    # print(f"[D16] E_sum={sum(w['E'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    # print(f"[D17] total_D={total_D}", file=sys.stderr, flush=True)
    # print(f"[D18] total_E={total_E}", file=sys.stderr, flush=True)
    # print(f"[D19] quit_new_total_D={quit_new_total_D}", file=sys.stderr, flush=True)
    # print(f"[D20] quit_new_total_E={quit_new_total_E}", file=sys.stderr, flush=True)
    # print(f"[D21] all_total_D={all_total_D}", file=sys.stderr, flush=True)
    # print(f"[D22] all_total_E={all_total_E}", file=sys.stderr, flush=True)
    # print(f"[D1] D: sum={sum(w['D'] for w in nurse_wallets.values())}, total={total_D}", file=sys.stderr, flush=True)
    # print(f"[D2] E: sum={sum(w['E'] for w in nurse_wallets.values())}, total={total_E}", file=sys.stderr, flush=True)
    # print(f"[D3] N: sum={sum(w['N'] for w in nurse_wallets.values())}, total={total_N}", file=sys.stderr, flush=True)
    # print(f"[D4] X: sum={sum(w['X'] for w in nurse_wallets.values())}, total={total_X}", file=sys.stderr, flush=True)
    # print(f"[D5] per: D={per_nurse_D}, E={per_nurse_E}, N={per_nurse_N}, X={per_nurse_X}", file=sys.stderr, flush=True)
    print(f"[D01] quit_list_len={len(quit_nurses_list)}", file=sys.stderr, flush=True)
    print(f"[D02] new_list_len={len(new_nurses_list)}", file=sys.stderr, flush=True)
    for q in quit_nurses_list:
        print(f"[D03] quit: {q.get('name')}, last={q.get('last_day')}, n={q.get('n_count')}", file=sys.stderr, flush=True)
    print(f"[D04] quit_new_total_D={quit_new_total_D}", file=sys.stderr, flush=True)
    print(f"[D05] quit_new_total_E={quit_new_total_E}", file=sys.stderr, flush=True)
    print(f"[D06] quit_new_total_X={quit_new_total_X}", file=sys.stderr, flush=True)
    print(f"[D07] total_X={total_X}", file=sys.stderr, flush=True)
    print(f"[D08] all_total_X={all_total_X}", file=sys.stderr, flush=True)
    print(f"[D09] num_all={num_all}", file=sys.stderr, flush=True)
    print(f"[D10] per_nurse_X={per_nurse_X}", file=sys.stderr, flush=True)
    print(f"[D11] D_sum={sum(w['D'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    print(f"[D12] E_sum={sum(w['E'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    print(f"[D13] N_sum={sum(w['N'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    print(f"[D14] X_sum={sum(w['X'] for w in nurse_wallets.values())}", file=sys.stderr, flush=True)
    for name, w in nurse_wallets.items():
        if name in quit_nurse_names:
            print(f"[D15] quit_wallet: {name}, X={w['X']}", file=sys.stderr, flush=True)
    ### debug
    
    # Deduct preferences from wallets
    preferences = data.get('preferences', [])
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                if duty in nurse_wallets[name]:
                    nurse_wallets[name][duty] -= 1
    
    # Debug disabled
    # print("[DEBUG] nurse_wallets after new/quit/preference adjustments:", file=sys.stderr)
    # for name, wallet in nurse_wallets.items():
    #     print(f"  {name}: {wallet}", file=sys.stderr)
    
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
    
    # max_consecutive_work already extracted earlier (before new/quit wallet calculation)
    # Just for reference: max_consecutive_work = data.get('max_consecutive_work', 6)
    
    # Extract min_N for Constraint 3 (min_N 보장용)
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
        'min_N': min_N_value
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
    
    # Debug disabled
    # print(f"[DEBUG] CP-SAT start: {year}/{month} ({num_days} days)", file=sys.stderr)
    
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
    
    # Constraint 2: Satisfy daily_wallet
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # Constraint 3: Satisfy nurse_wallet (Keep type별 정확한 제약)
    min_N = parsed_data.get('min_N', 6)
    new_nurses_dict = parsed_data['new_nurses']
    quit_nurses_dict = parsed_data['quit_nurses']
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        keep_type = nurse_data.get('keep_type', 'All')
        
        is_new = nurse in new_nurses_dict
        is_quit = nurse in quit_nurses_dict
        
        for duty in duties:
            target = nurse_wallets[nurse][duty]
            actual = sum(x[nurse][day][duty] for day in days)
            
            # 신규/퇴사 간호사: n_count 정확히 맞춤
            if is_new or is_quit:
                n_count_target = new_nurses_dict[nurse]['n_count'] if is_new else quit_nurses_dict[nurse]['n_count']
                
                if duty == 'N':
                    ### model.Add(actual == n_count_target) ### 정확한 값 포기
                    model.Add(actual >= n_count_target - 1) ###
                    model.Add(actual <= n_count_target + 1) ###    
                elif duty == 'X':
                    # X: 하한 없음, 상한만
                    model.Add(actual <= target + 1)
                else:
                    # D, E: ±1 허용
                    model.Add(actual >= target - 1)
                    model.Add(actual <= target + 1)
            
            # Night샤 (기존 근무자)
            elif keep_type == 'NightFixed':
                if duty == 'N':
                    # N = 15 (법적 기준) 정확히
                    model.Add(actual == NIGHT_KEEP_N_COUNT)
                elif duty == 'D' or duty == 'E':
                    # D, E는 0
                    model.Add(actual == 0)
                else:
                    # X: 하한 없음, 상한만
                    model.Add(actual <= target + 1)
            
            # Day샤 (기존 근무자)
            elif keep_type == 'DayFixed':
                if duty == 'N':
                    # N은 0
                    model.Add(actual == 0)
                elif duty == 'E':
                    # E도 0
                    model.Add(actual == 0)
                else:
                    # D는 ±1, X는 상한만
                    if duty == 'D':
                        model.Add(actual >= target - 1)
                        model.Add(actual <= target + 1)
                    else:  # X
                        model.Add(actual <= target + 1)
            
            # All 타입 (기존 근무자)
            else:
                if duty == 'N':
                    # N: min_N 이상 (단, 퇴사자/신규는 wallet 값 사용)
                    if nurse in quit_nurses or nurse in new_nurses:
                        model.Add(actual >= target - 1)
                    else:
                        model.Add(actual >= min_N)
                    model.Add(actual <= target + 1)
                elif duty == 'X':
                    # X: 하한 없음, 상한만
                    model.Add(actual <= target + 1)
                else:
                    # D, E: ±1 허용
                    model.Add(actual >= target - 1)
                    model.Add(actual <= target + 1)
    
    
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
    
    # Constraint 5: New nurses
    for name, data in new_nurses.items():
        start_day = data['start_day']
        # Before start: X
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
        # 첫날 D 강제 제거됨
        # - All: 자유롭게 D/E/N 배정
        # - DayKeep: Constraint 7에서 E/N=0이므로 D만 가능
        # - NightKeep: Constraint 7에서 D/E=0이므로 N만 가능
    
    # Constraint 6: Quit nurses
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        # After last day: X
        for day in range(last_day + 1, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # Constraint 7: Keep type restrictions
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'DayFixed':
            # Exclude E, N
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'NightFixed':
            # Exclude D, E
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # Constraint 8: zRule (check all consecutive 3-day windows)
    # z value calculation: 16*day1 + 4*day2 + 1*day3
    # Windows: (-3,-2,-1), (-2,-1,1), (-1,1,2), (1,2,3), ..., (29,30,31)
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        # Generate all consecutive 3-day windows
        all_windows = []
        all_windows.append((-3, -2, -1))
        all_windows.append((-2, -1, 1))
        all_windows.append((-1, 1, 2))
        for start in range(1, num_days - 1):
            all_windows.append((start, start + 1, start + 2))
        
        # Apply zRule to each 3-day window
        for d1, d2, d3 in all_windows:
            # Calculate next work day
            # Special case: past_3days windows (-3,-2,-1), (-2,-1,1), (-1,1,2)
            if d3 == -1:
                next_day = 1  # past_3days window: next day is day 1
            elif d3 < 1:
                continue  # Skip incomplete past windows
            else:
                next_day = d3 + 1
            
            if next_day < 1 or next_day > num_days:
                continue
            
            # Determine duty sources for each day
            duty_srcs = []
            for d in [d1, d2, d3]:
                if d < 0:
                    idx = d + 3  # -3->0, -2->1, -1->2
                    duty_srcs.append(('fixed', past_3days[idx]))
                else:
                    duty_srcs.append(('var', d))
            
            # Check all possible patterns (0~63)
            for z_val in range(64):
                # Reverse calculate pattern from z value
                z_temp = z_val
                req = []
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d3
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d2
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d1
                req.reverse()  # [d1, d2, d3]
                
                # Check pattern match
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
                
                # Check if pattern is in Z_RULES
                if z_val not in Z_RULES:
                    # Forbidden pattern: Add constraint to prevent this pattern
                    if len(match_vars) == 0:
                        # Fixed pattern is forbidden -> input validation error
                        # (should be caught by validate_input)
                        pass
                    else:
                        # Contains variables -> prevent this pattern from matching
                        match_all = model.NewBoolVar(f'forbidden_z_{nurse}_{d1}_{d2}_{d3}_{z_val}')
                        model.Add(sum(match_vars) == len(match_vars)).OnlyEnforceIf(match_all)
                        model.Add(sum(match_vars) < len(match_vars)).OnlyEnforceIf(match_all.Not())
                        
                        # Forbid this pattern
                        model.Add(match_all == 0)
                    continue
                
                # Allowed pattern: next_day can only be in allowed list
                allowed = Z_RULES[z_val]
                
                # Constraint: If pattern matches, next_day must be in allowed
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
    # Low Grade nurses cannot be on the same duty (D/E/N) on the same day
    low_grade_nurses = parsed_data.get('low_grade_nurses', [])
    
    if len(low_grade_nurses) >= 2:
        for day in days:
            for duty in ['D', 'E', 'N']:  # X is excluded
                model.Add(sum(x[nurse][day][duty] for nurse in low_grade_nurses) <= 1)

    # Constraint 10: Maximum Consecutive Work Days (Sliding Window)
    # 사용자가 N일 입력 → (N+1)일 윈도우마다 X >= 1개
    max_consecutive_work = parsed_data.get('max_consecutive_work', 6)
    window_size = max_consecutive_work + 1  # 예: 6 입력 → 7일 윈도우
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        # 현재 월 내에서 슬라이딩 윈도우 체크 (1 ~ num_days)
        for start_day in range(1, num_days - window_size + 2):
            end_day = start_day + window_size - 1
            
            if end_day > num_days:
                break
            
            # start_day ~ end_day 범위에서 X >= 1
            model.Add(
                sum(x[nurse][day]['X'] for day in range(start_day, end_day + 1)) >= 1
            )
        
        # 월초: past_3days와 연결되는 윈도우 체크
        # past_3days에서 X 개수 확인
        past_x_count = sum(1 for d in past_3days if d == 'X')
        
        if past_x_count == 0:
            # past_3days에 X 없음 → 1일부터 (window_size - 3)일 내에 X 필요
            # 예: window_size=7, past_3days에 X 없음 → 1~4일 내에 X >= 1
            remaining_window = window_size - 3
            if remaining_window > 0 and remaining_window <= num_days:
                model.Add(
                    sum(x[nurse][day]['X'] for day in range(1, remaining_window + 1)) >= 1
                )

    model.Minimize(0)
    
    # Run solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0  # Render timeout handling
    solver.parameters.num_search_workers = 4  # Memory conservation
    solver.parameters.log_search_progress = False  # Minimize logs
    
    # Random seed for diverse solutions
    # Each run explores different search paths, returning different valid schedules
    solver.parameters.random_seed = random.randint(1, 100000)
    
    # Early failure detection
    solver.parameters.cp_model_presolve = True
    solver.parameters.cp_model_probing_level = 2
    
    # Debug disabled
    # print("[DEBUG] CP-SAT solver running...", file=sys.stderr)
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # Solution found
        # print(f"[DEBUG] Solution found! (status={status})", file=sys.stderr)
        
        # Extract result
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
        # Error message
        error_msg = {
            cp_model.INFEASIBLE: "No feasible solution found (constraints cannot be satisfied)",
            cp_model.MODEL_INVALID: "Model is invalid (model error)",
            cp_model.UNKNOWN: "Solver status unknown (timeout or unknown error)"
        }.get(status, f"Solver failed with status {status}")
        
        # Input summary - get actual daily_wallet values from day 1 (representative)
        total_nurses = len(nurses)
        day1_wallet = daily_wallet.get(1, {})
        
        # Find first weekend day for weekend wallet
        weekend_wallet = {}
        for d in range(1, num_days + 1):
            if calendar.weekday(year, month, d) >= 5:  # Saturday or Sunday
                weekend_wallet = daily_wallet.get(d, {})
                break
        
        input_summary = [
            f"Nurses: {total_nurses}",
            f"Day1 wallet: D={day1_wallet.get('D',0)}, E={day1_wallet.get('E',0)}, N={day1_wallet.get('N',0)}, X={day1_wallet.get('X',0)}",
            f"Weekend wallet: D={weekend_wallet.get('D',0)}, E={weekend_wallet.get('E',0)}, N={weekend_wallet.get('N',0)}, X={weekend_wallet.get('X',0)}",
            f"Day1 total: {sum(day1_wallet.values()) if day1_wallet else 0}",
            f"Weekend total: {sum(weekend_wallet.values()) if weekend_wallet else 0}",
        ]
        
        # Suggestions
        suggestions = [
            "If nurse count is less than required staff, schedule is impossible",
            "Check if weekday/weekend staff sum equals total nurse count",
            "If past_3days has forbidden pattern (N-D-N, D-N-D, etc.), next day constraint may be violated",
            "If nurse_wallet min N is too high, schedule is impossible",
            "Too many preferences may cause conflicts",
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
    
    # Immediate logging before parsing (to debug timeout issues)
    try:
        raw_data = json.loads(input_json)
        dwc = raw_data.get('daily_wallet_config', {})
        ### print(f"[IMMEDIATE] daily_wallet_config.weekday: {dwc.get('weekday', 'MISSING')}", file=sys.stderr)
        ### print(f"[IMMEDIATE] daily_wallet_config.weekend: {dwc.get('weekend', 'MISSING')}", file=sys.stderr)
        ### print(f"[IMMEDIATE] nurse_wallet_min: {raw_data.get('nurse_wallet_min', 'MISSING')}", file=sys.stderr)
        sys.stderr.flush()
    except:
        pass
    
    try:
        # Parse and validate
        parsed_data = parse_input(input_json)
        
        # Run solver
        result, solver = solve_cpsat(parsed_data)
        
        # Validate result
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
        }, ensure_ascii=False, indent=2))  # stdout으로 출력
        sys.exit(1)
    
    except RuntimeError as e:
        print(json.dumps({
            'status': 'solver_error',
            'message': str(e)
        }, ensure_ascii=False, indent=2))  # stdout으로 출력
        sys.exit(1)
    
    except Exception as e:
        import traceback
        print(json.dumps({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, ensure_ascii=False, indent=2))  # stdout으로 출력
        sys.exit(1)


if __name__ == "__main__":
    main()

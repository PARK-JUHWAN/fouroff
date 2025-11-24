#!/usr/bin/env python3
"""
fouroff_ver_8.py - ì˜¬ë°”ë¥¸ wallet ê³„ì‚° (N+1, X+1 í¬í•¨)
"""

import json
import sys
import calendar
import holidays
from collections import defaultdict
from ortools.sat.python import cp_model


# ========================================
# Z_RULES (64ê°œ - All Soft Constraints)
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
    """ìž…ë ¥ ë°ì´í„° ê²€ì¦"""
    errors = []
    
    year = data['year']
    month = data['month']
    num_days = parsed_data['num_days']
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # past_3days ê²€ì¦
    for nurse_data in nurses_data:
        name = nurse_data['name']
        past = nurse_data.get('past_3days', [])
        
        if len(past) != 3:
            errors.append(f"{name}: past_3days must have exactly 3 elements")
        
        for i, duty in enumerate(past):
            if duty not in ['D', 'E', 'N', 'X']:
                errors.append(f"{name}: past_3days[{i}] invalid duty '{duty}'")
    
    # daily_wallet í•©ê³„ ê²€ì¦
    daily_wallet = parsed_data['daily_wallet']
    for day, wallet in daily_wallet.items():
        total = sum(wallet.values())
        if total != nurse_count:
            errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    
    # ë‚ ì§œ ë²”ìœ„ ê²€ì¦
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
    
    # preference ì¶©ëŒ ê²€ì¦
    preferences = parsed_data['preferences']
    
    # daily_wallet ì´ˆê³¼ ê²€ì¦
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
    """ê²°ê³¼ ê²€ì¦"""
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
    
    # ì¼ë³„ ê·¼ë¬´ ì¹´ìš´íŠ¸
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
    
    # ê°„í˜¸ì‚¬ë³„ ê·¼ë¬´ ì¹´ìš´íŠ¸
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # nurse_wallet ë§Œì¡± ì—¬ë¶€ (Â±1 í—ˆìš©)
        if nurse in nurse_wallets:
            for duty in ['D', 'E', 'N', 'X']:
                expected = nurse_wallets[nurse][duty]
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}Â±1, got {actual}"
                    )
            
            # Nì— ëŒ€í•œ ì—„ê²©í•œ ê²€ì¦
            if 'N' in duty_count:
                expected_N = nurse_wallets[nurse]['N']
                actual_N = duty_count['N']
                remaining_N = expected_N - actual_N
                
                if remaining_N >= 2:
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse}: N ë¶€ì¡± (ë‚¨ì€ N: {remaining_N}, ëª©í‘œ: <=1)"
                    )
    
    return validation


# ========================================
# Parse Input
# ========================================

def parse_input(input_json):
    """JSON ìž…ë ¥ íŒŒì‹± ë° wallet ê³„ì‚°"""
    data = json.loads(input_json)
    
    year = data['year']
    month = data['month']
    num_days = calendar.monthrange(year, month)[1]
    
    # ëŒ€í•œë¯¼êµ­ ê³µíœ´ì¼
    kr_holidays = holidays.KR(years=year)
    
    # daily_wallet ìƒì„±
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
    
    # nurse_wallet ê³„ì‚°
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Keep íƒ€ìž…ë³„ ê°„í˜¸ì‚¬ ìˆ˜ ì¹´ìš´íŠ¸
    all_nurses = []
    day_keep_nurses = []
    night_keep_nurses = []
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'Dayã…¤':
            day_keep_nurses.append(name)
        elif keep_type == 'Nightã…¤':
            night_keep_nurses.append(name)
        else:
            all_nurses.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all = len(all_nurses)
    
    print(f"[DEBUG] Keep íƒ€ìž… ë¶„í¬: All={num_all}, Dayã…¤={num_day_keep}, Nightã…¤={num_night_keep}", file=sys.stderr)
    
    # ì´ D, E, N, X ê³„ì‚°
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    print(f"[DEBUG] í•„ìš” ì´í•©: D={total_D}, E={total_E}, N={total_N}, X={total_X}", file=sys.stderr)
    
    # nurse_wallets ê³„ì‚°
    nurse_wallets = {}
    
    # Dayã…¤: Dë§Œ, E/N=0
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'D': num_days,
            'E': 0,
            'N': 0,
            'X': 2  # ì—¬ìœ ë¶„
        }
    
    # Nightã…¤: N=15, D/E=0
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'D': 0,
            'E': 0,
            'N': 15,
            'X': num_days - 15 + 2  # ì—¬ìœ ë¶„
        }
    
    # All íƒ€ìž…: ê· ë“± ë¶„ë°° + N+1, X+1 ì—¬ìœ ë¶„
    if num_all > 0:
        # Dayã…¤ì´ ì‚¬ìš©í•˜ëŠ” ì´ D
        day_keep_total_D = num_day_keep * num_days
        
        # Nightã…¤ì´ ì‚¬ìš©í•˜ëŠ” ì´ N
        night_keep_total_N = num_night_keep * 15
        
        # All íƒ€ìž…ì´ ì‚¬ìš©í•´ì•¼ í•˜ëŠ” D, E, N, X
        all_total_D = total_D - day_keep_total_D
        all_total_E = total_E
        all_total_N = total_N - night_keep_total_N
        all_total_X = total_X
        
        print(f"[DEBUG] All íƒ€ìž…ì´ ì‚¬ìš©í•´ì•¼ í•˜ëŠ” ê·¼ë¬´: D={all_total_D}, E={all_total_E}, N={all_total_N}, X={all_total_X}", file=sys.stderr)
        
        # nurse_wallet_minì—ì„œ min_N ê°€ì ¸ì˜¤ê¸°
        nurse_wallet_min = data.get('nurse_wallet_min', {})
        min_N = nurse_wallet_min.get('N', 6)
        
        # ê· ë“± ë¶„ë°°
        per_nurse_D = all_total_D // num_all
        per_nurse_E = all_total_E // num_all
        per_nurse_N = min_N + 1  # N+1
        per_nurse_X = (all_total_X // num_all) + 1  # X+1
        
        # ë‚˜ë¨¸ì§€ ë¶„ë°°
        remainder_D = all_total_D % num_all
        remainder_E = all_total_E % num_all
        
        print(f"[DEBUG] ê¸°ë³¸ í• ë‹¹: D={per_nurse_D}, E={per_nurse_E}, N={per_nurse_N}(min+1), X={per_nurse_X}(+1)", file=sys.stderr)
        
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

    
    print("[DEBUG] nurse_wallets ê³„ì‚° ì™„ë£Œ:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # ì‹ ê·œ/í‡´ì‚¬ ê°„í˜¸ì‚¬ wallet ì¡°ì •
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data['start_day']
        n_count = new_data['n_count']
        
        work_days = num_days - start_day + 1
        
        # ì‹ ê·œ: XëŠ” ì¶œê·¼ ì „, Nì€ ì§€ì •ê°’
        nurse_wallets[name]['X'] = start_day - 1 + nurse_wallets[name]['X']
        nurse_wallets[name]['N'] = n_count
        
        # D, E ìž¬ê³„ì‚°
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
        
        # í‡´ì‚¬: XëŠ” í‡´ì‚¬ í›„, Nì€ ì§€ì •ê°’
        nurse_wallets[name]['X'] += (num_days - last_day)
        nurse_wallets[name]['N'] = n_count
        
        # D, E ìž¬ê³„ì‚°
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        quit_nurses[name] = {'last_day': last_day, 'n_count': n_count}
    
    # preferencesì—ì„œ ì°¨ê°
    preferences = data.get('preferences', [])
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                if duty in nurse_wallets[name]:
                    nurse_wallets[name][duty] -= 1
    
    print("[DEBUG] ì‹ ê·œ/í‡´ì‚¬/í¬ë§ ë°˜ì˜ í›„ nurse_wallets:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # ê²€ì¦ ìˆ˜í–‰
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
        raise ValueError("ìž…ë ¥ ê²€ì¦ ì‹¤íŒ¨:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return parsed_data


# ========================================
# CP-SAT Solver
# ========================================

def solve_cpsat(parsed_data):
    """CP-SATë¡œ ê·¼ë¬´í‘œ ìƒì„±"""
    year = parsed_data['year']
    month = parsed_data['month']
    num_days = parsed_data['num_days']
    daily_wallet = parsed_data['daily_wallet']
    nurse_wallets = parsed_data['nurse_wallets']
    new_nurses = parsed_data['new_nurses']
    quit_nurses = parsed_data['quit_nurses']
    preferences = parsed_data['preferences']
    nurses_data = parsed_data['nurses_data']
    
    print(f"[DEBUG] CP-SAT ì‹œìž‘: {year}ë…„ {month}ì›” ({num_days}ì¼)", file=sys.stderr)
    
    nurses = list(nurse_wallets.keys())
    days = list(range(1, num_days + 1))
    duties = ['D', 'E', 'N', 'X']
    
    model = cp_model.CpModel()
    
    # ë³€ìˆ˜ ìƒì„±
    x = {}
    for nurse in nurses:
        x[nurse] = {}
        for day in days:
            x[nurse][day] = {}
            for duty in duties:
                x[nurse][day][duty] = model.NewBoolVar(f'{nurse}_d{day}_{duty}')
    
    # ì œì•½ 1: í•˜ë£¨ì— í•˜ë‚˜ì˜ ê·¼ë¬´ë§Œ
    for nurse in nurses:
        for day in days:
            model.Add(sum(x[nurse][day][duty] for duty in duties) == 1)
    
    # ì œì•½ 2: daily_wallet ë§Œì¡±
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # ì œì•½ 3: nurse_wallet ë§Œì¡± (Â±1 í—ˆìš©)
    for nurse in nurses:
        for duty in duties:
            target = nurse_wallets[nurse][duty]
            actual = sum(x[nurse][day][duty] for day in days)
            model.Add(actual >= target - 1)
            model.Add(actual <= target + 1)
    
    # ì œì•½ 4: í¬ë§ ê·¼ë¬´ ê³ ì •
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
    
    # ì œì•½ 5: ì‹ ê·œ ê°„í˜¸ì‚¬
    for name, data in new_nurses.items():
        start_day = data['start_day']
        # ì¶œê·¼ ì „: X
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
        # ì²«ë‚ : D
        if start_day in days:
            model.Add(x[name][start_day]['D'] == 1)
    
    # ì œì•½ 6: í‡´ì‚¬ ê°„í˜¸ì‚¬
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        # í‡´ì‚¬ í›„: X
        for day in range(last_day, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # ì œì•½ 7: Keep íƒ€ìž…
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'Dayã…¤':
            # E, N ì œì™¸
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'Nightã…¤':
            # D, E ì œì™¸
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # 제약 8: zRule (과거 3일 근무에 따른 허용 근무)
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        for day in days:
            # 현재 날짜의 이전 3일 근무 확인
            prev_duties = []
            for offset in range(3):
                prev_day = day - 3 + offset
                if prev_day < 1:
                    # past_3days에서 가져오기
                    idx = prev_day + 3  # -2→1, -1→2, 0→3 (하지만 0은 사용 안 함)
                    if idx >= 0 and idx < 3:
                        prev_duties.append(past_3days[idx])
                    elif prev_day == 0:
                        # day 0은 존재하지 않으므로 스킵
                        continue
                else:
                    # 실제 날짜 변수 사용
                    prev_duties.append(None)  # 나중에 처리
            
            # prev_duties가 완전하지 않으면 스킵 (첫날 등)
            if len(prev_duties) != 3 or None in prev_duties:
                # 첫날은 past_3days로만 처리
                if day == 1:
                    z_val = sum(WEIGHT[past_3days[i]] * (4 ** i) for i in range(3))
                    if z_val in Z_RULES:
                        allowed = Z_RULES[z_val]
                        for duty in duties:
                            if duty not in allowed:
                                model.Add(x[nurse][day][duty] == 0)
                continue
            
            # zRule 적용 (day >= 4만)
            if day >= 4:
                for z_val, allowed in Z_RULES.items():
                    # z값을 past3로 변환
                    z_temp = z_val
                    required_past = []
                    for _ in range(3):
                        required_past.append(["D", "E", "N", "X"][z_temp % 4])
                        z_temp //= 4
                    
                    # 이전 3일이 required_past와 일치하는지 확인
                    match_vars = []
                    for offset in range(3):
                        prev_day = day - 3 + offset
                        req_duty = required_past[offset]
                        match_vars.append(x[nurse][prev_day][req_duty])
                    
                    # 모든 match_vars가 1이면 allowed만 허용
                    match_all = model.NewBoolVar(f'match_{nurse}_d{day}_z{z_val}')
                    model.Add(sum(match_vars) == 3).OnlyEnforceIf(match_all)
                    model.Add(sum(match_vars) < 3).OnlyEnforceIf(match_all.Not())
                    
                    # match_all이 True이면 allowed 외의 근무 금지
                    for duty in duties:
                        if duty not in allowed:
                            model.Add(x[nurse][day][duty] == 0).OnlyEnforceIf(match_all)
    
    # ëª©ì í•¨ìˆ˜: ìµœì†Œí™” (ì—†ìŒ)
    model.Minimize(0)
    
    # ì†”ë²„ ì‹¤í–‰
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 8
    
    print("[DEBUG] CP-SAT ì†”ë²„ ì‹¤í–‰ ì¤‘...", file=sys.stderr)
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"[DEBUG] í•´ê²°ì±… ë°œê²¬! (status={status})", file=sys.stderr)
        
        # ê²°ê³¼ ì¶”ì¶œ
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
    """ë©”ì¸ ì‹¤í–‰"""
    if len(sys.argv) > 1:
        input_json = sys.argv[1]
    else:
        input_json = sys.stdin.read()
    
    try:
        # íŒŒì‹± ë° ê²€ì¦
        parsed_data = parse_input(input_json)
        
        # ì†”ë²„ ì‹¤í–‰
        result, solver = solve_cpsat(parsed_data)
        
        # ê²°ê³¼ ê²€ì¦
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

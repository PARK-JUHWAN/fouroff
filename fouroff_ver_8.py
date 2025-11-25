#!/usr/bin/env python3
# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
"""
fouroff_ver_8.py - 시뮬레이션 wallet 계산 (N+1, X+1 허용)
"""

import json
import sys
import calendar
import holidays
from collections import defaultdict
from ortools.sat.python import cp_model


# ========================================
# Z_RULES (64개 - All Soft Constraints)
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

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
def validate_input(data, parsed_data):
    """입력 데이터 검증"""
    errors = []
    
    year = data['year']
    month = data['month']
    num_days = parsed_data['num_days']
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # toClaude: KOREAN_PROTECTED - past_3days 검증
    for nurse_data in nurses_data:
        name = nurse_data['name']
        past = nurse_data.get('past_3days', [])
        
        if len(past) != 3:
            errors.append(f"{name}: past_3days must have exactly 3 elements")
        
        for i, duty in enumerate(past):
            if duty not in ['D', 'E', 'N', 'X']:
                errors.append(f"{name}: past_3days[{i}] invalid duty '{duty}'")
        
        # toClaude: KOREAN_PROTECTED - past_3days가 Z_RULES에 있는지 포함여부인지 확인
        if len(past) == 3 and all(d in ['D', 'E', 'N', 'X'] for d in past):
            z = 16 * WEIGHT[past[0]] + 4 * WEIGHT[past[1]] + 1 * WEIGHT[past[2]]
            if z not in Z_RULES:
                pattern = f"{past[0]}-{past[1]}-{past[2]}"
                errors.append(
                    f"{name}: past_3days pattern {pattern} (z={z}) is not allowed by Z_RULES. "
                    f"This pattern is forbidden and cannot occur."
                )
    
    # toClaude: KOREAN_PROTECTED - daily_wallet 확인 검증
    daily_wallet = parsed_data['daily_wallet']
    for day, wallet in daily_wallet.items():
        total = sum(wallet.values())
        if total != nurse_count:
            errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    
    # toClaude: KOREAN_PROTECTED - 날짜 범위 검증
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
    
    # toClaude: KOREAN_PROTECTED - preference 충돌 검증
    preferences = parsed_data['preferences']
    
    # toClaude: KOREAN_PROTECTED - daily_wallet 초과 검증
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


# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
def validate_result(result, parsed_data):
    """결과 검증"""
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
    
    # toClaude: KOREAN_PROTECTED - 일별 근무 카운트 확인
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
    
    # toClaude: KOREAN_PROTECTED - 간호사별 근무 카운트 확인
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # toClaude: KOREAN_PROTECTED - nurse_wallet 만족 여부 (±1 허용)
        if nurse in nurse_wallets:
            for duty in ['D', 'E', 'N', 'X']:
                expected = nurse_wallets[nurse][duty]
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}±1, got {actual}"
                    )
            
            # toClaude: KOREAN_PROTECTED - N의 남은횟수 사전검증 확인
            if 'N' in duty_count:
                expected_N = nurse_wallets[nurse]['N']
                actual_N = duty_count['N']
                remaining_N = expected_N - actual_N
                
                if remaining_N >= 2:
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse}: N 부족 (남은 N: {remaining_N}, 목표: <=1)"
                    )
    
    return validation


# ========================================
# Parse Input
# ========================================

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
def parse_input(input_json):
    """JSON 입력 파싱 및 wallet 계산"""
    data = json.loads(input_json)
    
    year = data['year']
    month = data['month']
    num_days = calendar.monthrange(year, month)[1]
    
    # toClaude: KOREAN_PROTECTED - 대한민국 공휴일
    kr_holidays = holidays.KR(years=year)
    
    # toClaude: KOREAN_PROTECTED - daily_wallet 생성
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
    
    # toClaude: KOREAN_PROTECTED - nurse_wallet 계산
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # toClaude: KOREAN_PROTECTED - Keep 타입별 간호사 위치 확인
    all_nurses = []
    day_keep_nurses = []
    night_keep_nurses = []
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'Day고정':
            day_keep_nurses.append(name)
        elif keep_type == 'Night고정':
            night_keep_nurses.append(name)
        else:
            all_nurses.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all = len(all_nurses)
    
    # toClaude: KOREAN_PROTECTED - Keep 타입별 분류
    print(f"[DEBUG] Keep 타입별 분류: All={num_all}, Day고정={num_day_keep}, Night고정={num_night_keep}", file=sys.stderr)
    
    # toClaude: KOREAN_PROTECTED - 월 D, E, N, X 계산
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    # toClaude: KOREAN_PROTECTED - 합계 월별필요
    print(f"[DEBUG] 합계 월별필요: D={total_D}, E={total_E}, N={total_N}, X={total_X}", file=sys.stderr)
    
    # toClaude: KOREAN_PROTECTED - nurse_wallets 계산
    nurse_wallets = {}
    
    # toClaude: KOREAN_PROTECTED - Day고정: D만, E/N=0
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'D': num_days,
            'E': 0,
            'N': 0,
            'X': 2  # 주당 분할
        }
    
    # toClaude: KOREAN_PROTECTED - Night고정: N=15, D/E=0
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'D': 0,
            'E': 0,
            'N': 15,
            'X': num_days - 15 + 2  # 주당 분할
        }
    
    # toClaude: KOREAN_PROTECTED - All 타입별: 균등 분배 + N+1, X+1 주당 분할
    if num_all > 0:
        # toClaude: KOREAN_PROTECTED - Day고정의 사용량에 따른 월 D
        day_keep_total_D = num_day_keep * num_days
        
        # toClaude: KOREAN_PROTECTED - Night고정의 사용량에 따른 월 N
        night_keep_total_N = num_night_keep * 15
        
        # toClaude: KOREAN_PROTECTED - All 타입별의 사용량이야 할당해 D, E, N, X
        all_total_D = total_D - day_keep_total_D
        all_total_E = total_E
        all_total_N = total_N - night_keep_total_N
        all_total_X = total_X
        
        # toClaude: KOREAN_PROTECTED - All 타입별의 사용량이야 할당해 균등
        print(f"[DEBUG] All 타입별의 사용량이야 할당해 균등: D={all_total_D}, E={all_total_E}, N={all_total_N}, X={all_total_X}", file=sys.stderr)
        
        # toClaude: KOREAN_PROTECTED - nurse_wallet_min에서 min_N 가져오기
        nurse_wallet_min = data.get('nurse_wallet_min', {})
        min_N = nurse_wallet_min.get('N', 6)
        
        # toClaude: KOREAN_PROTECTED - 균등 분배
        per_nurse_D = all_total_D // num_all
        per_nurse_E = all_total_E // num_all
        per_nurse_N = min_N + 1  # N+1
        per_nurse_X = (all_total_X // num_all) + 1  # X+1
        
        # toClaude: KOREAN_PROTECTED - 나머지 분배
        remainder_D = all_total_D % num_all
        remainder_E = all_total_E % num_all
        
        # toClaude: KOREAN_PROTECTED - 기본 할당
        print(f"[DEBUG] 기본 할당: D={per_nurse_D}, E={per_nurse_E}, N={per_nurse_N}(min+1), X={per_nurse_X}(+1)", file=sys.stderr)
        
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

    
    # toClaude: KOREAN_PROTECTED - nurse_wallets 계산 완료
    print("[DEBUG] nurse_wallets 계산 완료:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # toClaude: KOREAN_PROTECTED - 신규/퇴사 간호사 wallet 조정
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data.get('start_day')
        n_count = new_data.get('n_count', 0)
        
        
        # toClaude: KOREAN_PROTECTED - start_day가 None이면 건너뛰기
        if start_day is None:
            print(f"[WARNING] 신규 간호사 {name}의 start_day가 없어서 건너뜁니다", file=sys.stderr)
            continue
        
        work_days = num_days - start_day + 1
        
        # toClaude: KOREAN_PROTECTED - 신규: X로 출근 전, N의 지정값
        nurse_wallets[name]['X'] = start_day - 1 + nurse_wallets[name]['X']
        nurse_wallets[name]['N'] = n_count
        
        # toClaude: KOREAN_PROTECTED - D, E 재계산
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        new_nurses[name] = {'start_day': start_day, 'n_count': n_count}
    
    quit_nurses = {}
    for quit_data in quit_nurses_list:
        name = quit_data['name']
        last_day = quit_data.get('last_day')
        n_count = quit_data.get('n_count', 0)
        
        
        # toClaude: KOREAN_PROTECTED - last_day가 None이면 건너뛰기
        if last_day is None:
            print(f"[WARNING] 퇴사 간호사 {name}의 last_day가 없어서 건너뜁니다", file=sys.stderr)
            continue
        
        work_days = last_day
        
        # toClaude: KOREAN_PROTECTED - 퇴사: X로 퇴사 후, N의 지정값
        nurse_wallets[name]['X'] += (num_days - last_day)
        nurse_wallets[name]['N'] = n_count
        
        # toClaude: KOREAN_PROTECTED - D, E 재계산
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        quit_nurses[name] = {'last_day': last_day, 'n_count': n_count}
    
    # toClaude: KOREAN_PROTECTED - preferences에서 참조
    preferences = data.get('preferences', [])
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                if duty in nurse_wallets[name]:
                    nurse_wallets[name][duty] -= 1
    
    # toClaude: KOREAN_PROTECTED - 신규/퇴사/희망 반영 후 nurse_wallets
    print("[DEBUG] 신규/퇴사/희망 반영 후 nurse_wallets:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # toClaude: KOREAN_PROTECTED - 검증 실행
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
        raise ValueError("입력 검증 실패:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return parsed_data


# ========================================
# CP-SAT Solver
# ========================================

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
def solve_cpsat(parsed_data):
    """CP-SAT로 근무표 생성"""
    year = parsed_data['year']
    month = parsed_data['month']
    num_days = parsed_data['num_days']
    daily_wallet = parsed_data['daily_wallet']
    nurse_wallets = parsed_data['nurse_wallets']
    new_nurses = parsed_data['new_nurses']
    quit_nurses = parsed_data['quit_nurses']
    preferences = parsed_data['preferences']
    nurses_data = parsed_data['nurses_data']
    
    # toClaude: KOREAN_PROTECTED - CP-SAT 시작
    print(f"[DEBUG] CP-SAT 시작: {year}년 {month}월 ({num_days}일)", file=sys.stderr)
    
    nurses = list(nurse_wallets.keys())
    days = list(range(1, num_days + 1))
    duties = ['D', 'E', 'N', 'X']
    
    model = cp_model.CpModel()
    
    # toClaude: KOREAN_PROTECTED - 변수 생성
    x = {}
    for nurse in nurses:
        x[nurse] = {}
        for day in days:
            x[nurse][day] = {}
            for duty in duties:
                x[nurse][day][duty] = model.NewBoolVar(f'{nurse}_d{day}_{duty}')
    
    # toClaude: KOREAN_PROTECTED - 제약 1: 하루에 하나의 근무만
    for nurse in nurses:
        for day in days:
            model.Add(sum(x[nurse][day][duty] for duty in duties) == 1)
    
    # toClaude: KOREAN_PROTECTED - 제약 2: daily_wallet 만족
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # toClaude: KOREAN_PROTECTED - 제약 3: nurse_wallet 만족 (±1 허용)
    for nurse in nurses:
        for duty in duties:
            target = nurse_wallets[nurse][duty]
            actual = sum(x[nurse][day][duty] for day in days)
            model.Add(actual >= target - 1)
            model.Add(actual <= target + 1)
    
    # toClaude: KOREAN_PROTECTED - 제약 4: 희망 근무 고정
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
    
    # toClaude: KOREAN_PROTECTED - 제약 5: 신규 간호사
    for name, data in new_nurses.items():
        start_day = data['start_day']
        # toClaude: KOREAN_PROTECTED - 출근 전: X
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
        # toClaude: KOREAN_PROTECTED - 첫날: D
        if start_day in days:
            model.Add(x[name][start_day]['D'] == 1)
    
    # toClaude: KOREAN_PROTECTED - 제약 6: 퇴사 간호사
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        # toClaude: KOREAN_PROTECTED - 퇴사 후: X
        for day in range(last_day, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # toClaude: KOREAN_PROTECTED - 제약 7: Keep 타입별
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'Day고정':
            # toClaude: KOREAN_PROTECTED - E, N 제외
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'Night고정':
            # toClaude: KOREAN_PROTECTED - D, E 제외
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # toClaude: KOREAN_PROTECTED - 제약 8: zRule (모든 3일 연속 구간 검사)
    # toClaude: KOREAN_PROTECTED - z값 계산: 16*첫날 + 4*둘째날 + 1*셋째날
    # toClaude: KOREAN_PROTECTED - 구간: (-3,-2,-1), (-2,-1,1), (-1,1,2), (1,2,3), ..., (29,30,31)
    
    for nurse in nurses:
        nurse_data = next(n for n in nurses_data if n['name'] == nurse)
        past_3days = nurse_data['past_3days']
        
        # toClaude: KOREAN_PROTECTED - 모든 3일 연속 구간 생성
        all_windows = []
        all_windows.append((-3, -2, -1))
        all_windows.append((-2, -1, 1))
        all_windows.append((-1, 1, 2))
        for start in range(1, num_days - 1):
            all_windows.append((start, start + 1, start + 2))
        
        # toClaude: KOREAN_PROTECTED - 각 3일 구간에 zRule 적용
        for d1, d2, d3 in all_windows:
            # toClaude: KOREAN_PROTECTED - 다음 근무일 계산
            next_day = d3 + 1
            if next_day < 1 or next_day > num_days:
                continue
            
            # toClaude: KOREAN_PROTECTED - 각 날짜 근무 타입
            duty_srcs = []
            for d in [d1, d2, d3]:
                if d < 0:
                    idx = d + 3  # -3→0, -2→1, -1→2
                    duty_srcs.append(('fixed', past_3days[idx]))
                else:
                    duty_srcs.append(('var', d))
            
            # toClaude: KOREAN_PROTECTED - 모든 가능한 패턴(0~63) 검사
            for z_val in range(64):
                # toClaude: KOREAN_PROTECTED - z값 → 패턴 역산
                z_temp = z_val
                req = []
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d3
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d2
                z_temp //= 4
                req.append(["D", "E", "N", "X"][z_temp % 4])  # d1
                req.reverse()  # [d1, d2, d3]
                
                # toClaude: KOREAN_PROTECTED - 매칭 확인
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
                
                # toClaude: KOREAN_PROTECTED - Z_RULES에 있는지 확인
                if z_val not in Z_RULES:
                    # toClaude: KOREAN_PROTECTED - 금지된 패턴: 이 패턴이 발생하지 못하도록 제약
                    if len(match_vars) == 0:
                        # toClaude: KOREAN_PROTECTED - fixed 패턴이 금지된 패턴 → 입력 검증 오류
                        # (이미 validate_input에서 걸려야 함)
                        pass
                    else:
                        # toClaude: KOREAN_PROTECTED - 변수 포함 → 이 패턴이 매칭되지 않도록
                        match_all = model.NewBoolVar(f'forbidden_z_{nurse}_{d1}_{d2}_{d3}_{z_val}')
                        model.Add(sum(match_vars) == len(match_vars)).OnlyEnforceIf(match_all)
                        model.Add(sum(match_vars) < len(match_vars)).OnlyEnforceIf(match_all.Not())
                        
                        # toClaude: KOREAN_PROTECTED - 금지된 패턴 발생 금지
                        model.Add(match_all == 0)
                    continue
                
                # toClaude: KOREAN_PROTECTED - 허용된 패턴: next_day는 allowed만
                allowed = Z_RULES[z_val]
                
                # toClaude: KOREAN_PROTECTED - 제약: 패턴 매칭 시 next_day는 allowed만
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
    
    # toClaude: KOREAN_PROTECTED - 솔버 실행
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0  # Render timeout 대응
    solver.parameters.num_search_workers = 4  # 메모리 절약
    solver.parameters.log_search_progress = False  # 로그 최소화
    
    # toClaude: KOREAN_PROTECTED - 조기 실패 감지
    solver.parameters.cp_model_presolve = True
    solver.parameters.cp_model_probing_level = 2
    
    # toClaude: KOREAN_PROTECTED - 솔버 실행 중
    print("[DEBUG] CP-SAT 솔버 실행 중...", file=sys.stderr)
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        # toClaude: KOREAN_PROTECTED - 해결책 발견
        print(f"[DEBUG] 해결책 발견! (status={status})", file=sys.stderr)
        
        # toClaude: KOREAN_PROTECTED - 결과 추출
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
        # toClaude: KOREAN_PROTECTED - 에러 메시지
        error_msg = {
            cp_model.INFEASIBLE: "No feasible solution found (제약 조건을 만족하는 해가 없음)",
            cp_model.MODEL_INVALID: "Model is invalid (모델 오류)",
            cp_model.UNKNOWN: "Solver status unknown (시간 초과 또는 알 수 없는 오류)"
        }.get(status, f"Solver failed with status {status}")
        
        # toClaude: KOREAN_PROTECTED - 입력 값 요약
        total_nurses = len(nurses)
        weekday_staff = daily_wallet.get('weekday', {})
        weekend_staff = daily_wallet.get('weekend', {})
        
        input_summary = [
            f"Nurses: {total_nurses}명",
            f"Weekday staff: D={weekday_staff.get('D',0)}, E={weekday_staff.get('E',0)}, N={weekday_staff.get('N',0)}",
            f"Weekend staff: D={weekend_staff.get('D',0)}, E={weekend_staff.get('E',0)}, N={weekend_staff.get('N',0)}",
            f"Total weekday required: {sum(weekday_staff.values())}",
            f"Total weekend required: {sum(weekend_staff.values())}",
        ]
        
        # toClaude: KOREAN_PROTECTED - 권장 조치
        suggestions = [
            "간호사 수가 요구 인원보다 적으면 불가능합니다",
            "평일/주말 인원 합계가 전체 간호사 수와 같은지 확인하세요",
            "past_3days가 금지된 패턴(N-D-N, D-N-D 등)이면 다음날 제약 위배 가능",
            "nurse_wallet의 최소 N 개수가 너무 많으면 불가능합니다",
            "희망 근무(preferences)가 너무 많으면 충돌 가능성 높음",
        ]
        
        raise RuntimeError(
            f"{error_msg}\n\n입력 요약:\n" + 
            "\n".join(f"  {s}" for s in input_summary) +
            "\n\n권장 조치:\n" + 
            "\n".join(f"  - {s}" for s in suggestions)
        )


# ========================================
# Main
# ========================================

# toClaude: KOREAN_PROTECTED - No sed, use str_replace only
def main():
    """메인 실행"""
    if len(sys.argv) > 1:
        input_json = sys.argv[1]
    else:
        input_json = sys.stdin.read()
    
    try:
        # toClaude: KOREAN_PROTECTED - 파싱 및 검증
        parsed_data = parse_input(input_json)
        
        # toClaude: KOREAN_PROTECTED - 솔버 실행
        result, solver = solve_cpsat(parsed_data)
        
        # toClaude: KOREAN_PROTECTED - 결과 검증
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

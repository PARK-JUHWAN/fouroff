#!/usr/bin/env python3
"""
fouroff_ver_8.py - Day킵 wallet 조정 버전
- (1) Day킵 존재 시 All 타입의 D 감소 로직 추가
- 테스트 코드 제거, 디버깅 출력 추가
- Render API 서버 연동 준비
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

def validate_input(data, parsed_data):
    """입력 데이터 검증 (2,3,6,7,11,12,13)"""
    errors = []
    
    year = data['year']
    month = data['month']
    num_days = parsed_data['num_days']
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # 6. past_3days 검증
    for nurse_data in nurses_data:
        name = nurse_data['name']
        past = nurse_data.get('past_3days', [])
        
        if len(past) != 3:
            errors.append(f"{name}: past_3days must have exactly 3 elements (got {len(past)})")
        
        for i, duty in enumerate(past):
            if duty not in ['D', 'E', 'N', 'X']:
                errors.append(f"{name}: past_3days[{i}] has invalid duty '{duty}'")
    
    # 2. daily_wallet 합계 검증
    daily_wallet = parsed_data['daily_wallet']
    for day, wallet in daily_wallet.items():
        total = sum(wallet.values())
        if total != nurse_count:
            errors.append(f"Day {day}: daily_wallet sum ({total}) != nurse count ({nurse_count})")
    
    # 3. nurse_wallet 총합 검증
    expected_total = num_days + 2
    nurse_wallets = parsed_data['nurse_wallets']
    for name, wallet in nurse_wallets.items():
        total = sum(wallet.values())
        if total != expected_total:
            errors.append(f"{name}: nurse_wallet sum ({total}) != expected ({expected_total})")
    
    # 7. 날짜 범위 검증
    new_nurses = parsed_data['new_nurses']
    for name, info in new_nurses.items():
        start_day = info['start_day']
        if not (1 <= start_day <= num_days):
            errors.append(f"{name}: start_day ({start_day}) out of range [1, {num_days}]")
    
    quit_nurses = parsed_data['quit_nurses']
    for name, info in quit_nurses.items():
        last_day = info['last_day']
        if not (1 <= last_day <= num_days):
            errors.append(f"{name}: last_day ({last_day}) out of range [1, {num_days}]")
    
    # 5,10,11,12,13. 희망 근무 충돌 검증
    preferences = parsed_data['preferences']
    
    # 5. daily_wallet 초과 검증
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
    
    # 10. nurse_wallet 초과 검증
    nurse_pref_count = defaultdict(lambda: defaultdict(int))
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        for day_str, duty in schedule.items():
            nurse_pref_count[name][duty] += 1
    
    for name, duty_counts in nurse_pref_count.items():
        if name not in nurse_wallets:
            continue
        
        for duty, count in duty_counts.items():
            available = nurse_wallets[name].get(duty, 0)
            if count > available:
                errors.append(
                    f"{name}: wants {duty} {count} times but only has {available} in wallet"
                )
    
    # 11. 신규 첫날 D 충돌 검증
    for name, info in new_nurses.items():
        start_day = info['start_day']
        
        # 첫날 희망 근무 확인
        pref = next((p for p in preferences if p['name'] == name), None)
        if pref:
            schedule = pref.get('schedule', {})
            first_day_pref = schedule.get(str(start_day))
            
            if first_day_pref and first_day_pref != 'D':
                errors.append(
                    f"{name}: first day (day {start_day}) must be 'D' but prefers '{first_day_pref}'"
                )
    
    # 12. 퇴사 범위 희망 근무 검증
    for name, info in quit_nurses.items():
        last_day = info['last_day']
        
        pref = next((p for p in preferences if p['name'] == name), None)
        if pref:
            schedule = pref.get('schedule', {})
            
            for day_str in schedule.keys():
                day = int(day_str)
                if day >= last_day:
                    errors.append(
                        f"{name}: quit on day {last_day} but has preference on day {day}"
                    )
    
    # 13. Keep 타입-희망 근무 충돌 검증
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        pref = next((p for p in preferences if p['name'] == name), None)
        if pref:
            schedule = pref.get('schedule', {})
            
            for day_str, duty in schedule.items():
                if keep_type == 'Day킵':
                    if duty not in ['D', 'X']:
                        errors.append(
                            f"{name}: Day킵 but wants '{duty}' on day {day_str} (only D/X allowed)"
                        )
                
                elif keep_type == 'Night킵':
                    if duty not in ['N', 'X']:
                        errors.append(
                            f"{name}: Night킵 but wants '{duty}' on day {day_str} (only N/X allowed)"
                        )
    
    return errors


def validate_result(result, parsed_data):
    """결과 검증 (8)"""
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
    
    # 일별 근무 카운트
    for day in range(1, num_days + 1):
        day_count = defaultdict(int)
        
        for nurse, schedule in result.items():
            duty = schedule.get(str(day))
            if duty:
                day_count[duty] += 1
        
        # daily_wallet 만족 여부
        for duty in ['D', 'E', 'N', 'X']:
            expected = daily_wallet[day][duty]
            actual = day_count[duty]
            
            if actual != expected:
                validation['daily_wallet_satisfied'] = False
                validation['daily_violations'].append(
                    f"Day {day} {duty}: expected {expected}, got {actual}"
                )
    
    # 간호사별 근무 카운트
    for nurse, schedule in result.items():
        duty_count = defaultdict(int)
        
        for day in range(1, num_days + 1):
            duty = schedule.get(str(day))
            if duty:
                duty_count[duty] += 1
        
        validation['nurse_duty_counts'][nurse] = dict(duty_count)
        
        # nurse_wallet 만족 여부 (±1 허용)
        if nurse in nurse_wallets:
            for duty in ['D', 'E', 'N', 'X']:
                expected = nurse_wallets[nurse][duty]
                actual = duty_count[duty]
                
                if not (expected - 1 <= actual <= expected + 1):
                    validation['nurse_wallet_satisfied'] = False
                    validation['nurse_violations'].append(
                        f"{nurse} {duty}: expected {expected}±1, got {actual}"
                    )
    
    return validation


# ========================================
# Parse Input
# ========================================

def parse_input(input_json):
    """JSON 입력 파싱 및 wallet 계산"""
    data = json.loads(input_json)
    
    year = data['year']
    month = data['month']
    num_days = calendar.monthrange(year, month)[1]
    
    # 대한민국 공휴일
    kr_holidays = holidays.KR(years=year)
    
    # daily_wallet 생성
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
    
    # nurse_wallet 계산
    nurses_data = data['nurses']
    nurse_count = len(nurses_data)
    
    # Keep 타입별 간호사 수 카운트
    all_nurses = []
    day_keep_nurses = []
    night_keep_nurses = []
    
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'Day킵':
            day_keep_nurses.append(name)
        elif keep_type == 'Night킵':
            night_keep_nurses.append(name)
        else:
            all_nurses.append(name)
    
    num_day_keep = len(day_keep_nurses)
    num_night_keep = len(night_keep_nurses)
    num_all = len(all_nurses)
    
    print(f"[DEBUG] Keep 타입 분포: All={num_all}, Day킵={num_day_keep}, Night킵={num_night_keep}", file=sys.stderr)
    
    # 총 D, E, N, X 계산
    total_D = sum(daily_wallet[day]['D'] for day in range(1, num_days + 1))
    total_E = sum(daily_wallet[day]['E'] for day in range(1, num_days + 1))
    total_N = sum(daily_wallet[day]['N'] for day in range(1, num_days + 1))
    total_X = sum(daily_wallet[day]['X'] for day in range(1, num_days + 1))
    
    print(f"[DEBUG] 필요 총합: D={total_D}, E={total_E}, N={total_N}, X={total_X}", file=sys.stderr)
    
    # (1) Day킵 고려한 wallet 계산
    nurse_wallets = {}
    
    # Day킵: D만, E/N=0
    for name in day_keep_nurses:
        nurse_wallets[name] = {
            'D': num_days,
            'E': 0,
            'N': 0,
            'X': 2  # 여유분
        }
    
    # Night킵: N=15, D/E=0
    for name in night_keep_nurses:
        nurse_wallets[name] = {
            'D': 0,
            'E': 0,
            'N': 15,
            'X': num_days - 15 + 2
        }
    
    # All 타입: D/E 분배, Day킵 수만큼 D 감소
    if num_all > 0:
        # Day킵이 사용하는 총 D
        day_keep_total_D = num_day_keep * num_days
        
        # Night킵이 사용하는 총 N
        night_keep_total_N = num_night_keep * 15
        
        # All 타입이 사용해야 하는 D, E, N
        all_total_D = total_D - day_keep_total_D
        all_total_E = total_E
        all_total_N = total_N - night_keep_total_N
        
        print(f"[DEBUG] All 타입이 사용해야 하는 근무: D={all_total_D}, E={all_total_E}, N={all_total_N}", file=sys.stderr)
        
        # 기본 N (nurse_wallet_min['N'] + 1)
        base_N = data.get('nurse_wallet_min', {}).get('N', 6) + 1
        
        # 각 All 간호사의 wallet
        per_nurse_N = base_N
        per_nurse_D = all_total_D // num_all
        per_nurse_E = all_total_E // num_all
        
        # 나머지 분배
        remainder_D = all_total_D % num_all
        remainder_E = all_total_E % num_all
        
        for i, name in enumerate(all_nurses):
            d_count = per_nurse_D + (1 if i < remainder_D else 0)
            e_count = per_nurse_E + (1 if i < remainder_E else 0)
            
            nurse_wallets[name] = {
                'D': d_count,
                'E': e_count,
                'N': per_nurse_N,
                'X': num_days - d_count - e_count - per_nurse_N + 2
            }
    
    print("[DEBUG] nurse_wallets 계산 완료:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # 신규/퇴사 간호사 wallet 조정
    new_nurses_list = data.get('new', [])
    quit_nurses_list = data.get('quit', [])
    
    new_nurses = {}
    for new_data in new_nurses_list:
        name = new_data['name']
        start_day = new_data['start_day']
        n_count = new_data['n_count']
        
        work_days = num_days - start_day + 1
        
        # 신규: X는 출근 전, N은 지정값
        nurse_wallets[name]['X'] = start_day - 1 + nurse_wallets[name]['X']
        nurse_wallets[name]['N'] = n_count
        
        # D, E 재계산
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
        
        # 퇴사: X는 퇴사 후, N은 지정값
        nurse_wallets[name]['X'] += (num_days - last_day)
        nurse_wallets[name]['N'] = n_count
        
        # D, E 재계산
        remaining = work_days - n_count
        nurse_wallets[name]['D'] = remaining // 2
        nurse_wallets[name]['E'] = remaining - nurse_wallets[name]['D']
        
        quit_nurses[name] = {'last_day': last_day, 'n_count': n_count}
    
    # preferences에서 차감
    preferences = data.get('preferences', [])
    for pref in preferences:
        name = pref['name']
        schedule = pref.get('schedule', {})
        
        if name in nurse_wallets:
            for day_str, duty in schedule.items():
                if duty in nurse_wallets[name]:
                    nurse_wallets[name][duty] -= 1
    
    print("[DEBUG] 신규/퇴사/희망 반영 후 nurse_wallets:", file=sys.stderr)
    for name, wallet in nurse_wallets.items():
        print(f"  {name}: {wallet}", file=sys.stderr)
    
    # 검증 수행
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
    
    print(f"[DEBUG] CP-SAT 시작: {year}년 {month}월 ({num_days}일)", file=sys.stderr)
    
    nurses = list(nurse_wallets.keys())
    days = list(range(1, num_days + 1))
    duties = ['D', 'E', 'N', 'X']
    
    model = cp_model.CpModel()
    
    # 변수 생성
    x = {}
    for nurse in nurses:
        x[nurse] = {}
        for day in days:
            x[nurse][day] = {}
            for duty in duties:
                x[nurse][day][duty] = model.NewBoolVar(f'{nurse}_d{day}_{duty}')
    
    # 제약 1: 하루에 하나의 근무만
    for nurse in nurses:
        for day in days:
            model.Add(sum(x[nurse][day][duty] for duty in duties) == 1)
    
    # 제약 2: daily_wallet 만족
    for day in days:
        for duty in duties:
            model.Add(sum(x[nurse][day][duty] for nurse in nurses) == daily_wallet[day][duty])
    
    # 제약 3: nurse_wallet 만족 (±1 허용)
    for nurse in nurses:
        for duty in duties:
            target = nurse_wallets[nurse][duty]
            actual = sum(x[nurse][day][duty] for day in days)
            model.Add(actual >= target - 1)
            model.Add(actual <= target + 1)
    
    # 제약 4: 희망 근무 고정
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
    
    # 제약 5: 신규 간호사
    for name, data in new_nurses.items():
        start_day = data['start_day']
        # 출근 전: X
        for day in range(1, start_day):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
        # 첫날: D
        if start_day in days:
            model.Add(x[name][start_day]['D'] == 1)
    
    # 제약 6: 퇴사 간호사
    for name, data in quit_nurses.items():
        last_day = data['last_day']
        # 퇴사 후: X
        for day in range(last_day, num_days + 1):
            if day in days:
                model.Add(x[name][day]['X'] == 1)
    
    # 제약 7: Keep 타입
    for nurse_data in nurses_data:
        name = nurse_data['name']
        keep_type = nurse_data.get('keep_type', 'All')
        
        if keep_type == 'Day킵':
            # E, N 제외
            for day in days:
                model.Add(x[name][day]['E'] == 0)
                model.Add(x[name][day]['N'] == 0)
        
        elif keep_type == 'Night킵':
            # D, E 제외
            for day in days:
                model.Add(x[name][day]['D'] == 0)
                model.Add(x[name][day]['E'] == 0)
    
    # 제약 8: Z_RULES (Soft) - 임시 비활성화
    z_violations = []
    # TODO: Z_RULES 활성화 후 테스트
    
    # 목적함수: z_rule 위반 최소화
    model.Minimize(sum(z_violations))
    
    # 솔버 실행
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 8
    
    print("[DEBUG] CP-SAT 솔버 실행 중...", file=sys.stderr)
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"[DEBUG] 해결책 발견! (status={status})", file=sys.stderr)
        
        # 결과 추출
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
            "Check nurse_wallet totals equal num_days + 2",
            "Check preference conflicts (too many nurses want same duty)",
            "Try relaxing Z_RULES or nurse_wallet constraints"
        ]
        
        raise RuntimeError(
            f"{error_msg}\n\nSuggestions:\n" + 
            "\n".join(f"  - {s}" for s in suggestions)
        )


# ========================================
# Main (테스트 코드 제거)
# ========================================

def main():
    """메인 실행 - stdin에서 JSON 입력 받기"""
    if len(sys.argv) > 1:
        # 명령줄 인자로 JSON 받기
        input_json = sys.argv[1]
    else:
        # stdin에서 JSON 받기
        input_json = sys.stdin.read()
    
    try:
        # 파싱 및 검증
        parsed_data = parse_input(input_json)
        
        # 솔버 실행
        result, solver = solve_cpsat(parsed_data)
        
        # 결과 검증
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

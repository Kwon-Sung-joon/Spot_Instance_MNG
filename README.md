
# Spot Instance With AutoScalingGroups
![image](https://github.com/Kwon-Sung-joon/Spot_Instance_MNG/assets/43159901/314bfdb2-5d8c-4136-8be0-ac7e355fb3eb)


# Spot Insatnce MNG 동작 방식

1. Alert 발생
- EC2 Instance Rebalance Recommendation or Spot Instance interruptions

2. Spot Instance 생성 요청
  - 성공 :  스팟 인스턴스 생성
  - 실패 : 온디맨스 인스턴스 생성 또는 다른 타입, 다른 가용 영역의 인스턴스 검토

3. Alert 발생한 대상 Spot Instance ID SQS 적재
- 대상 Spot Instance를 일정 시간 이후(e.g. 1분) AutoScalingGroup에서 분리하기 위함


4. SQS delay queue를 사용하여 대상 Spot Instance를 해당 AutoScalingGroup에서 분리
- delay queue는 0초 ~ 15분 내로 선택 가능


5. 분리된 Spot Insatnce를 회수 대상으로만 구성된  AutoScalingGroup에 등록
- 해당 AutoScalingGroup은 매 분마다 등록된 인스턴스를 삭제하도록 스케줄 등록
- Spot Insatnce 회수에 관련된 알람 구성 가능

6. 해당 Spot Instance 로그 적재 후 제거
- AutoScalingGroup Terminate Lifecycle Hooks 사용


## 검토 사항

- Spot Instances 다중 회수 시나리오를 생각하였을 땐 On-Demand로 운영되는 서버는 1~2대 유지 고려

- Capacity Rebalancing을 사용하였을 땐 worst 시나리오에서는 새로운 Spot Instance가 생성되지 않고 

- 장비가 회수 될 수 있으므로 직접 로직을 구성  
 → 로직 단계 별로 Alert을 받는 것 고려  
  대체 인스턴스 생성 여부 상관 없이 일정 시간 이후 회수 대상 Instance 서비스 분리  

- ASG에 등록된 AMI는 로그를 모두 정리하여 깨끗한 상태로 유지
-  → 장비 회수 시 로그 적재 과정 시간 단축 및 중복 로그 방지

- Scale-Out 할 때 서비스 기동 후 LB 등록까지의 시간 테스트 필요

- EC2 다중 타입 사용 시 정책 적용 테스트 필요


## 예상 시나리오
Case A.  
1. Rebalance Recommendation 발생

2. Scale-Out (Spot Instance)

3. Scale-Out 완료

4. Rebalance Recommendation 대상 Spot Instance 회수

Case B.  
1. Spot Instance interruptions, Rebalance Recommendation 동시 발생 (2분 후 Spot Instance 회수)

2. Scale-Out (Spot Instance) 

3. Spot Instance interruptions 대상 Spot Instance 회수  
→ Scale-Out 이후 서비스 기동 까지 2분 이내 완료 필요

Case C.  

1. Rebalance Recommendation 발생

2. Scale-Out (Spot Instance) → 대상 타입의 Spot Instance 요청 실패

3. Scale-Out (On-Demand)

4. Scale-Out 완료 (On-Demand)

5. Rebalance Recommendation 대상 Spot Instance 회수  
→ 실패한 Spot Instance 재시도 → 성공 → On-Demand Instance 종료

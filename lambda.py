import json
import boto3
import time

ASG_Spot_Pool='ASG_Prod_Spot_Instances'

class Asg:
    def __init__(self):
        self.ec2_client=boto3.client('ec2');
        self.asg_client=boto3.client('autoscaling');

    #get asg name of target instance
    def get_target(self,INSTANCE_ID): 
        ec2_info=self.ec2_client.describe_instances(InstanceIds=[INSTANCE_ID]);
        for tags in ec2_info['Reservations'][0]['Instances'][0]['Tags']:
            if tags['Key'] == 'aws:autoscaling:groupName':
                ASG_NAME=tags['Value']
        return ASG_NAME

    #increase asg spot or on-demand
    def increaseASG(self,ASG_NAME,IS_SPOT):
        asg_desc = self.asg_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                ASG_NAME
        ])

        #as-is spot instance capacity
        AS_IS=asg_desc['AutoScalingGroups'][0]['DesiredCapacity'];
        for i in asg_desc['AutoScalingGroups'][0]['Instances']:
            if i['LifecycleState'] == 'Detaching':
                AS_IS -= 1;
        #to-be spot instance capacity
        TO_BE=AS_IS+1
        
        #asg's launch template name
        LT_NAME=asg_desc['AutoScalingGroups'][0]['MixedInstancesPolicy']['LaunchTemplate']['LaunchTemplateSpecification']['LaunchTemplateName']
        
        #as-is on demand insatnces
        AS_IS_ON_DEMAND=asg_desc['AutoScalingGroups'][0]['MixedInstancesPolicy']['InstancesDistribution']['OnDemandBaseCapacity']

        #scale-out spot insatnce
        if IS_SPOT == True:
            print("Step2. Scale Out Spot Insatnces... {0} : {1} -> {2}".format(ASG_NAME,AS_IS,TO_BE))
            set_desired = self.asg_client.set_desired_capacity(
                AutoScalingGroupName=ASG_NAME,
                DesiredCapacity=TO_BE)

        #scale-out on-demand insatnce
        elif IS_SPOT == False:
            #create lt on-demand version
            #self.create_lt_version(LT_NAME);
            print("Step2. Scale Out On-Demand Insatnces... {0} : {1} -> {2}".format(ASG_NAME,AS_IS_ON_DEMAND,AS_IS_ON_DEMAND+1));
            response = self.asg_client.update_auto_scaling_group(
                AutoScalingGroupName=ASG_NAME,
                MixedInstancesPolicy={
                    'InstancesDistribution': {
                        'OnDemandBaseCapacity': AS_IS_ON_DEMAND+1,
                        }
                    },
            )
            #delete lt on-demand version
            #self.delete_lt_version(LT_NAME);

    #detach reblance spot instance
    def detach_target(self,INSTANCE_ID,ASG_NAME):
        response = self.asg_client.detach_instances(
            InstanceIds=[
                INSTANCE_ID,
                ],
                AutoScalingGroupName=ASG_NAME,
                ShouldDecrementDesiredCapacity=True
        )
    
    #terminate rebalnce spot instance
    def terminate_target(self,INSTANCE_ID,ASG_NAME):
        FLAG = False
        while FLAG == False:
            ARR_INSTANCES=[]
            asg=self.asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[ASG_NAME,])
            time.sleep(3);

            for i in asg['AutoScalingGroups'][0]['Instances']:
            #if i['InstanceId'] == INSTANCE_ID and i['LifecycleState'] == 'Detaching':                
                ARR_INSTANCES.append(i['InstanceId']);

            if INSTANCE_ID in ARR_INSTANCES:
                print("");
                #print("EC2 {0} dose Detaching...".format(INSTANCE_ID));
            elif INSTANCE_ID not in ARR_INSTANCES:
                print("Step3. EC2 {0} dose Detached from {1}".format(INSTANCE_ID,ASG_NAME));
                FLAG=True;
                self.attach_to_garbage_group(INSTANCE_ID,ASG_Spot_Pool);
                break;
    
    #attach to rebalance spot instance group
    def attach_to_garbage_group(self,INSTANCE_ID,ASG_Spot_Pool):
        response = self.asg_client.attach_instances(
            InstanceIds=[
                INSTANCE_ID,
                ],
                AutoScalingGroupName=ASG_Spot_Pool
            )
        self.ec2_client.create_tags(
                Resources=[
                    INSTANCE_ID,
                    ],
                    Tags=[
                        {
                            'Key': 'DEPLOY_GROUP',
                            'Value': 'SPOT'
                            },
                        ]
                        )
        
    
    #create lt version
    def create_lt_version(self,LT_NAME):
        response = self.ec2_client.create_launch_template_version(
            LaunchTemplateName=LT_NAME,
            SourceVersion='$Latest',
            )
    #delete lt version
    def delete_lt_version(self,LT_NAME):
        response = self.ec2_client.delete_launch_template_versions(
            LaunchTemplateName=LT_NAME,
            Versions=[
                '$Latest',
                ]
        )

def lambda_handler(event, context):
    print(json.dumps(event));
    asg_client=Asg();

    try:
        #chk trigger is event or sqs msg.
        event['detail']
    #trigger is sqs msg
    except Exception:
        records=event.get('Records');
        body=json.loads(records[0].get('body'));
        detail=body.get('detail');
        detail_type=body.get('detail-type');
        ASG_NAME=asg_client.get_target(detail['instance-id']);


        if ASG_NAME == "ASG_Prod_Spot_Instances" :
            return 0;
        #elif detail_type == 'EC2 Spot Instance Interruption Warning':
        elif detail_type == 'EC2 Instance Rebalance Recommendation':            
            return detail_type;
        else:
            print("Terminate Spot Insatnce Step Starts !!!");
            print("Step1. terminating instance {0} after detach".format(detail['instance-id']))
            asg_client.detach_target(detail['instance-id'],ASG_NAME);
            print("Step2. target entering detaching from {0}".format(ASG_NAME))
            asg_client.terminate_target(detail['instance-id'],ASG_NAME);
            return 0;
            
            
    #trigger is event
    else:
        #spot insatnce rebalance
        if event['detail-type'] == 'EC2 Instance Rebalance Recommendation':
            return event['detail-type'];
        elif event['detail-type'] == 'EC2 Spot Instance Interruption Warning':
            print("Spot Insatnce Scale-Out Step Starts !!!");
            print("Step1. instance : {0} {1}...".format(event['detail']['instance-id'],event['detail-type']));
            ASG_NAME=asg_client.get_target(event['detail']['instance-id']);
            asg_client.increaseASG(ASG_NAME,True);

'''
        ##spot insatnce scale-out fail occurred -> scale-out on-demand instance
        else:
            print("Spot Insatnce Scale-Out Step Starts !!!");
            print("Step1. error occurred !!! errorCode : {0} , errorMessage: {1} ".format(event['detail']['errorCode'],event['detail']['errorMessage']));
            for tag in event['detail']['requestParameters']['tagSpecificationSet']['items'][0]['tags']:
                if tag['key']=='aws:autoscaling:groupName':
                    ASG_NAME=tag['value'];

            asg_client.increaseASG(ASG_NAME,False);
'''

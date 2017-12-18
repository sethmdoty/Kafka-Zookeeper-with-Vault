import json
import boto3
import botocore
from six.moves import urllib
import subprocess
import time
import paramiko

def determineNode(nodeList, max, region):
    sum = 0
    print('in determineNode')
    for item in nodeList:
        print('item is: '+str(item))
        # Grab tag value
        TAG = subprocess.check_output("aws ec2 describe-tags --profile=paul --filters \"Name=resource-id,Values="+item['InstanceId']+"\" \"Name=key,Values=Name\" --region="+REGION+" --output=text | cut -f5; echo",shell=True)
        TAG = TAG.replace('\n', '')
        TAG = TAG.strip()
        print("instance Tag is: "+TAG)
        try:
            sum = sum + int(TAG[-1:])
        except Exception as e:
            print(str(e))
        print('sum is: '+str(sum))

    # determine the sum of all nodes
    tSum = 0
    for i in range(max):
        tSum = tSum + i + 1

    # return the missing node
    sum = tSum - sum
    print('missing node is: '+str(sum))
    return sum

def getAWSValues():
    # Get the instances IP address
    localip = urllib.request.urlopen('http://169.254.169.254/latest/meta-data/local-ipv4').read()
    localip = localip.strip()
    print("instance IP is: "+localip)

    # Get the Instance Name tag value
    instanceid=subprocess.check_output("curl http://169.254.169.254/latest/meta-data/instance-id; echo",shell=True)
    instanceid = instanceid.strip()
    print("instance ID is: "+instanceid)

    # Get the region instanc eis in
    region = subprocess.check_output("curl -s3 http://169.254.169.254/latest/dynamic/instance-identity/document | grep region | awk -F: \'{print $2}\'; echo",shell=True)
    #print("region is: "+REGION)
    region = region.replace('"', '')
    region = region.replace(',', '')
    region = region.strip()
    print("region is: "+region)

    # Grab tag value
    tagvalue = subprocess.check_output("aws ec2 describe-tags --profile=paul --filters \"Name=resource-id,Values="+instanceid+"\" \"Name=key,Values=Name\" --region="+region+" --output=text | cut -f5; echo",shell=True)
    tagvalue = tagvalue.replace('\n', '')
    tagvalue = tagvalue.strip()
    print("instance Tag is: "+tagvalue)

    if tagvalue == '':
        print("there is no value for the instance tag, so wait and try again")
        time.sleep(180)
        tagvalue = subprocess.check_output("aws ec2 describe-tags --profile=paul --filters \"Name=resource-id,Values="+instanceid+"\" \"Name=key,Values=Name\" --region="+region+" --output=text | cut -f5; echo",shell=True)
        tagvalue = tagvalue.replace('\n', '')
        tagvalue = tagvalue.strip()
        print("instance Tag is: "+tagvalue)
        if tagvalue == '':
            print("there is still no value for the instance tag, so assuming it is zookeeper")
            tagvalue = 'zookeeper'

    session = boto3.Session(profile_name='terraform')

    # get the ASG details for kafka and zookeeper
    asg = boto3.client('autoscaling')

    zkAsg = asg.describe_auto_scaling_groups(
        AutoScalingGroupNames=[
            'zookeeper_ASG',
        ]
    )
    print('the zookeeper ASGs are: '+str(zkAsg['AutoScalingGroups']))
    print('the zookeeper ASG details are: '+str(zkAsg['AutoScalingGroups'][0]['AutoScalingGroupName']))
    print('the zookeeper max instnces are: '+str(zkAsg['AutoScalingGroups'][0]['MaxSize']))
    zkmaxinstances = zkAsg['AutoScalingGroups'][0]['MaxSize']
    instancelist = zkAsg['AutoScalingGroups'][0]['Instances']

    return [localip, instanceid, tagvalue, zkmaxinstances, instancelist, region]

def getStateFile(table, maxinstances):
    #initialise the default json file
    state = {
        'state_name' : 'zookeeper',
        'changed'    : '',
        'nodes'      : 0
    }
    index = 0
    while index < maxinstances:
        index += 1
        state['zookeeper'+str(index)] = '0.0.0.0'

    print ('the default json data is: '+str(state))


    try:
        response = table.get_item(
            Key={
                'state_name': 'zookeeper'
            }
        )
        print('the dynamodb response is: '+str(response))
        state = response['Item']
        print('the state stored in the dynamodb table is: '+str(state))
    except Exception as e:
        print('the exception is: '+str(e))
        if str(e) == '\'Item\'':
            print('there is no item the first time the table is read, ignore')
        else:
            raise e

    print ('the converted state is: '+str(state))

    return state



def getS3StateFile(s3, maxinstances, bucket, file, path):
    #initialise the default json file
    state = {
        'changed'    : '',
        'nodes'      : 0
    }
    index = 0
    while index < maxinstances:
        index += 1
        state['zookeeper'+str(index)] = '0.0.0.0'

    print ('the default json data is: '+str(state))

    # Get file from S3 bucket
    try:
        s3.Bucket(bucket).download_file(file, path+filename)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist, so creating it")
            json.dump(state, open(path+file,'w'))
        else:
            raise

    #Read JSON data into the datastore variable
    state = json.load(open(path+file,'r'))
    print (state)

    return state


def changeTagName(tag, ip, state, list, maxinstances, region):
    # changing the default instance tag name to reflect the node in the ASG
    if tag == 'zookeeper':
        if state['nodes'] < maxinstances:
            print('changing name for initial node')
            tag = tag+str((state['nodes']+1))
            state['nodes'] = state['nodes']+1
        # if one of the nodes has died and been replaced in the ASG
        else:
            print('changing name for existing node')
            tag = tag+str(determineNode(list, maxinstances, region))
            print('TAG_VALUE is now: '+tag)
            state['nodes'] = state['nodes']+1

    # Update the JSON with the changed IP for the server
    print (state[tag])
    state[tag] = ip
    state['changed'] = tag
    print (state)

    return [tag, state]

if __name__ == "__main__":

    # initialise needed variables
    session = boto3.Session(profile_name='terraform')
    #s3 = session.resource('s3')
    # filename = 'zookeeper_ips.json'
    # path = '/tmp/install-zookeeper/'
    # bucket_name = 'zookeeper-bucket-pp'

    # get the AWS values needed to lookup the relevant state and ASG data
    valueList = getAWSValues()
    LOCAL_IP = valueList[0]
    INSTANCE_ID = valueList[1]
    TAG_VALUE = valueList[2]
    zkmaxInstances = valueList[3]
    instanceList = valueList[4]
    region = valueList[5]

    # get the current details from the cached S3 bucket
    #data = getS3StateFile(s3, zkmaxInstances, bucket_name, filename, path)

    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table('zookeeper-state')
    # get the current details from the DynamoDB table
    data = getStateFile(table, zkmaxInstances)


    # change the intances tag Name to reflect the node in the ASG
    retvals = changeTagName(TAG_VALUE, LOCAL_IP, data, instanceList, zkmaxInstances, region)
    TAG_VALUE = retvals[0]
    data = retvals[1]

    # Uploads the given file using a managed uploader, which will split up large
    # files automatically and upload parts in parallel
    table.put_item(Item = data)


    # Change the instance Name tag value
    ec2 = session.resource('ec2')
    ec2.create_tags(Resources=[INSTANCE_ID], Tags=[{'Key':'Name', 'Value':TAG_VALUE}])

    # stop zookeeper
    subprocess.check_output("sudo su ec2-user -c \'sudo service zookeeper stop\'", shell=True, executable='/bin/bash')

    # Update the /etc/hosts file
    # Add hosts entries (mocking DNS) - put relevant IPs here
    subprocess.check_output("sudo su ec2-user -c \'python /tmp/install-zookeeper/update_etc_hosts.py "+str(zkmaxInstances)+"\'", shell=True, executable='/bin/bash')

    # update the myId file
    node = TAG_VALUE[-1:]
    subprocess.check_output("echo \""+node+"\" > /data/zookeeper/myid", shell=True)

    # update the /etc/hosts on existing zookeeper nodes to reflect change on this node
    for key in data:
        jsonName = key.encode("utf-8")
        print('jsonName is: ')
        print(jsonName)
        print('node in data is: ')
        print(data[jsonName])
        if jsonName != TAG_VALUE and jsonName != 'changed' and jsonName != '' and jsonName != 'nodes' and jsonName != 'state_name' and data[jsonName] != '0.0.0.0':
            try:
                print('updating etc hosts on: '+jsonName)
                private_key = paramiko.RSAKey.from_private_key_file('/tmp/install-kafka/<your .pem file>')
                client = paramiko.client.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(jsonName, port=22, username='ec2-user', pkey=private_key)
                s = client.get_transport().open_session()
                s.exec_command("sudo su ec2-user -c \'python /tmp/install-zookeeper/update_etc_hosts.py "+str(zkmaxInstances)+"\'")
            except Exception as e:
                print(str(e))


    # start zookeeper
    subprocess.check_output("sudo su ec2-user -c \'sudo service zookeeper start\'", shell=True, executable='/bin/bash')
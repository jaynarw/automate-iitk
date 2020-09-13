import requests
from bs4 import BeautifulSoup
import json
from PyInquirer import prompt, print_json
import os
import re
import sys

# Get current directory
path = os.getcwd()
loggedIn = False
r = requests.Session()

while(loggedIn == False):
  loginQuestions = [
      {
          'type': 'input',
          'message': 'Enter your hello iitk username',
          'name': 'username'
      },
      {
          'type': 'password',
          'message': 'Enter your hello iitk password',
          'name': 'password'
      }
  ]

  loginAnswers = prompt(loginQuestions)


  payload= {
    'name': loginAnswers['username'],
    'pass': loginAnswers['password'],
    'form_id':'user_login_form',
    'op':'SIGN+IN'
  }
  ## Login to hello IITK
  x = r.post('https://hello.iitk.ac.in/user/login', data = payload)

  cookies = r.cookies.get_dict()
  if ('uid' in cookies and 'token' in cookies):
    loggedIn = True
  else:
    r.cookies.clear()
    print('Could not login, please retry')

cookies = r.cookies.get_dict()


## Retrieve course list
courseList = r.get('https://hello.iitk.ac.in/courses').content
courseData = {}
questions = [
    {
        'type': 'checkbox',
        'name': 'course_list',
        'message': 'Select coureses to download',
        'choices': [],
    },
    {
      'type': 'list',
      'name': 'type',
      'message': 'Download pdf or videos or both?',
      'choices': ['Both', 'Videos', 'PDFs'],
      'default': 2,
    }
]

soup = BeautifulSoup(courseList, features="html.parser")
courseElts = soup.select('.courses-grid-coulmn a')

courseNames = {}
for link in courseElts:
  questions[0]['choices'].append({
    'name': link.text.strip().replace('\n',' - '),
    'value': link.get('href').split('/')[-1]
  })
  courseNames[link.get('href').split('/')[-1]] = link.text.strip().replace('\n',' - ')

answers = prompt(questions)
print(answers)

def download(url, filename, folder, week, topic):
    os.makedirs(os.path.join(folder, week, topic ), exist_ok=True)
    with open(os.path.join(folder, week, topic, filename), 'wb') as f:
        response = requests.get(url, stream=True)
        total = response.headers.get('content-length')

        if total is None:
            f.write(response.content)
        else:
            downloaded = 0
            total = int(total)
            for data in response.iter_content(chunk_size=max(int(total/1000), 1024*1024)):
                downloaded += len(data)
                f.write(data)
                done = int(50*downloaded/total)
                sys.stdout.write('\r[{}{}]'.format('█' * done, '.' * (50-done)))
                sys.stdout.flush()
    sys.stdout.write('\n')

def videoHTML(url):
  return '''<html>
   <body>
      <script type="text/javascript">
    window.location.href = "{}"; //change this to the URL
                                                       //you want to redirect to
      </script>
   </body>
</html>'''.format(url)

for course in answers['course_list']:
  summaryURL = 'https://hello.iitk.ac.in/api/' + course + '/lectures/summary'
  data = json.loads(r.get(summaryURL, headers={
    'uid':cookies['uid'],
    'token':cookies['token'],
  }).content)
  folder = re.sub(r'[\\\/:*?"<>|]',' - ', courseNames[course])

  weekIdx = 0
  topicIdx = 0
  videoIdx = 0
  fileIdx = 0
  totalVids = 0
  totalPDFs = 0
  currIdx = 0
  courseData = {}
  for resource in data:
    if (resource['videoURL'] != None):
      totalVids += 1
    totalVids += len([v for v in resource['videosUploaded'] if v['type'] == 'original'])
    totalPDFs += len(resource['resources'])
  totalDownloads = totalPDFs + totalVids
  if answers['type'] == 'PDFs':
    totalDownloads = totalPDFs
  if answers['type'] == 'Videos':
    totalDownloads = totalVids
  for (idx, resource) in enumerate(data,1):
    week = resource['week']
    topic = resource['topic']
    week = re.sub(r'[\\\/:*?"<>|]',' - ', week)
    topic = re.sub(r'[\\\/:*?"<>|]',' - ', topic)
    if week not in courseData:
      courseData[week] = []
      weekIdx += 1
      topicIdx = 0
      videoIdx = 0
      fileIdx = 0
    if topic not in courseData[week]:
      courseData[week].append(topic)
      topicIdx = topicIdx + 1
      videoIdx = 0
      fileIdx = 0
    if(answers['type'] != 'PDFs'):
      if resource['videoURL'] != None:
        videoIdx = videoIdx + 1
        currIdx += 1
        os.makedirs(os.path.join(folder, week, str(topicIdx) + '_' + topic ), exist_ok=True)
        file = open(os.path.join(folder, week, str(topicIdx) + '_' + topic, str(videoIdx) + '_' + resource['title'] + '.' + 'html'), 'w+')
        file.write(videoHTML(resource['videoURL']))
        file.close()
      for video in [v for v in resource['videosUploaded'] if v['type'] == 'original']:
        videoIdx = videoIdx + 1
        currIdx += 1
        print('Downloading ' + resource['title'] + ' [' + str(currIdx) + '/' + str(totalDownloads) + ']' )
        download(video['path'], str(videoIdx) + '_' + resource['title'] + '.' + video['path'].split('.')[-1], folder, week, str(topicIdx) + '_' + topic)
    if(answers['type'] != 'Videos'):
      for file in resource['resources']:
        currIdx += 1
        fileIdx = fileIdx + 1
        print('Downloading ' + file['fileName'] + ' [' + str(currIdx) + '/' + str(totalDownloads) + ']' )
        download(file['fileURL'], str(fileIdx) + '_' + file['fileName'], folder, week, str(topicIdx) + '_' + topic)

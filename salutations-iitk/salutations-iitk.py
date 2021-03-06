import requests
from bs4 import BeautifulSoup
import json
from PyInquirer import prompt, print_json
import os
import re
import sys

def pathto_dict(path):
  for root, dirs, files in os.walk(path):
    tree = {}
    tree[os.path.basename(root)] = [pathto_dict(os.path.join(root, d)) for d in dirs]
    tree[os.path.basename(root)].extend(files)
    if len(files) == 0:
      temp = {}
      for i in tree[os.path.basename(root)]:
        key = list(dict.keys(i))[0]
        temp[key] = i[key]
        tree[os.path.basename(root)] = temp
    return tree

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

def courseToDirectory(data, minified=True):
  directory = {}
  for entry in data:
    week = purify_name(entry["week"])
    directory[week] = {}
    for (topicIdx, topicEntry) in enumerate(entry['lectures'], 1):
      topic = purify_name(topicEntry["topic"])
      directory[week]['{}_{}'.format(topicIdx, topic)] = []
      for (lecIdx, lec) in enumerate(topicEntry['lectures'], 1):
        pdfs = []
        for res in lec['resources']:
          # if res['fileName'] in 
          if minified:
            pdfs.append('{}_{}'.format(lecIdx, res['fileName']))
          else:
            pdfs.append(['{}_{}'.format(lecIdx, res['fileName']), res['fileURL'], 'file'])
        directory[week]['{}_{}'.format(topicIdx, topic)].extend(pdfs)
        title = lec['title']
        if lec['videoURL'] != None:
          if minified:
            directory[week]['{}_{}'.format(topicIdx, topic)].append('{}_{}.html'.format(lecIdx, title))
          else:
            directory[week]['{}_{}'.format(topicIdx, topic)].append(['{}_{}.html'.format(lecIdx, title), lec['videoURL'], 'url'])
        for video in lec['videosUploaded']:
          if video['type'] == 'original':
            name = '{}_{}'.format(lecIdx, title) + '.' + video['path'].split('.')[-1]
            name = purify_name(name)
            if minified:
              directory[week]['{}_{}'.format(topicIdx, topic)].append(name)
            else:
              directory[week]['{}_{}'.format(topicIdx, topic)].append([name, video['path'], 'video'])
  return directory

def pprint(x):
  print(json.dumps(x, indent=2, sort_keys=True))
def purify_name(x):
  return re.sub(r'[\\\/:*?"<>|]',' - ', x)

replace_question = [
    {
      'type': 'list',
      'name': 'action',
      'message': '',
      'choices': ['Replace', 'Replace All', 'Skip', 'Skip All'],
      'default': 2,
    }
]
replace_answer = {
  'action': None
}

def skip(folder, week, topic, file_name):
  global replace_answer
  if os.path.isfile(os.path.join(folder, week, topic, file_name)):
    if replace_answer['action'] == None:
      replace_question[0]["message"] = "File \"{} => {} => {} => {}\" already exists.. Download and Replace?".format(folder, week, topic, file_name)
      replace_answer = prompt(replace_question)
    if replace_answer['action'] == 'Skip':
      replace_answer['action'] = None
      return True
    elif replace_answer['action'] == 'Skip All':
      return True
    elif replace_answer['action'] == 'Replace':
      replace_answer['action'] = None
      return False
    else:
      return False
  else:
    return False


for course in answers['course_list']:
  summaryURL = 'https://hello.iitk.ac.in/api/' + course + '/lectures/summary'
  data = json.loads(r.get(summaryURL, headers={
    'uid':cookies['uid'],
    'token':cookies['token'],
  }).content)
  resourceURL = 'https://hello.iitk.ac.in/api/' + course + '/resources'
  resourceData = json.loads(r.get(resourceURL, headers={
    'uid':cookies['uid'],
    'token':cookies['token'],
  }).content)
  folder = re.sub(r'[\\\/:*?"<>|]',' - ', courseNames[course])

  ## Calculating Resources
  totalResources = 0
  for topic in resourceData:
    totalResources += len(topic['resources'])
  temp = []
  totalVids = 0
  totalPDFs = 0
  for res in data:
    if (res['videoURL'] != None):
      totalVids += 1
    totalVids += len([v for v in res['videosUploaded'] if v['type'] == 'original'])
    totalPDFs += len(res['resources'])
    toInsert = True
    for entry in temp:
      if entry['week'] == res['week']:
        entry['lectures'].append(res)
        toInsert = False
    if toInsert:
      temp.append({"week" : res['week'], 'lectures': [res]})
  for entry in temp:
    lecs = list(entry['lectures'])
    entry['lectures'] = []
    for lecture in lecs:
      topicExists = False
      for lec_2 in entry['lectures']:
        if lecture['topic'] == lec_2['topic']:
          topicExists = True
          lec_2['lectures'].append(lecture)
          break
      if topicExists == False:
        entry['lectures'].append({
          "topic": lecture['topic'],
          "lectures": list([lecture])
        })
  totalDownloads = totalPDFs + totalVids + totalResources
  if answers['type'] == 'PDFs':
    totalDownloads -= totalVids
  if answers['type'] == 'Videos':
    totalDownloads = totalPDFs
  formatted_data = courseToDirectory(temp, minified=False)
  curr_idx = 1
  for week in formatted_data:
    for topic in formatted_data[week]:
      for file_data in formatted_data[week][topic]:
        if file_data[2] == 'video' and answers['type'] != 'PDFs':
          if skip(folder, week, topic, file_data[0]):
            curr_idx+=1
            continue
          print('Downloading ' + file_data[0] + ' [' + str(curr_idx) + '/' + str(totalDownloads) + ']' )
          download(file_data[1], file_data[0], folder, week, topic)
        elif file_data[2] == 'url' and answers['type'] != 'PDFs':
          if skip(folder, week, topic, file_data[0]):
            curr_idx+=1
            continue
          os.makedirs(os.path.join(folder, week, topic ), exist_ok=True)
          file = open(os.path.join(folder, week, topic, file_data[0]), 'w+')
          file.write(videoHTML(file_data[1]))
          file.close()
        elif file_data[2] == 'file' and answers['type'] != 'Videos':
          if skip(folder, week, topic, file_data[0]):
            curr_idx+=1
            continue
          print('Downloading ' + file_data[0] + ' [' + str(curr_idx) + '/' + str(totalDownloads) + ']' )
          download(file_data[1], file_data[0], folder, week, topic)
        curr_idx += 1
  for (idx,topic) in enumerate(resourceData, 1):
    topicFolderName = purify_name('{}_{}'.format(idx, topic['title']))
    os.makedirs(os.path.join(folder, 'Resources', topicFolderName), exist_ok=True)
    for (resIdx, resource) in enumerate(topic['resources'], 1):
      if skip(folder, 'Resources', topicFolderName, resource['fileName']):
        curr_idx+=1
        continue
      print('Downloading ' + resource['fileName'] + ' [' + str(curr_idx) + '/' + str(totalDownloads) + ']' )
      download(resource['fileURL'], resource['fileName'], folder, 'Resources', topicFolderName)
      curr_idx+=1

def courseDirectoryMetadata(data, minified=True):
  directory = {}
  firstVideo = None
  prevLec = None
  # nextLec = None
  currLec = None
  for entry in data:
    week = purify_name(entry["week"])
    directory[week] = {}
    for (topicIdx, topicEntry) in enumerate(entry['lectures'], 1):
      topic = purify_name(topicEntry["topic"])
      directory[week]['{}_{}'.format(topicIdx, topic)] = {}
      for (lecIdx, lec) in enumerate(topicEntry['lectures'], 1):
        currLec = [week, '{}_{}'.format(topicIdx, topic)]
        for res in lec['resources']:
          directory[week]['{}_{}'.format(topicIdx, topic)]['{}_{}'.format(lecIdx, res['fileName'])] = {
            "fileName": '{}_{}'.format(lecIdx, res['fileName']),
            "type": "pdf",
          }

        title = lec['title']
        if lec['videoURL'] != None:
          fileName = '{}_{}'.format(lecIdx, title)
          currLec.append(fileName)
          directory[week]['{}_{}'.format(topicIdx, topic)][fileName] = {
            "URL": lec['videoURL'],
            "type": "url",
            "prevLec": prevLec,
            "nextLec": None
          }
          if prevLec:
            directory[prevLec[0]][prevLec[1]][prevLec[2]]["nextLec"] = currLec
          # Making prev
          prevLec = currLec
          currLec = None

        for video in lec['videosUploaded']:
          if video['type'] == 'original':
            name = '{}_{}'.format(lecIdx, title) + '.' + video['path'].split('.')[-1]
            name = purify_name(name)
            if firstVideo == None:
              firstVideo = [week, '{}_{}'.format(topicIdx, topic), name]
            directory[week]['{}_{}'.format(topicIdx, topic)][name] = {
              "fileName": name,
              "type": "mp4",
              "prevLec": prevLec,
              "nextLec": None
             }
            currLec.append(name)
            # Setting next of previous
            if prevLec:
              directory[prevLec[0]][prevLec[1]][prevLec[2]]["nextLec"] = currLec
            # Making prev
            prevLec = currLec
            currLec = None

  return directory, firstVideo


## Directory Metadata
Parsed_Data = {}
FirstVideos = []
for course in answers['course_list']:
  summaryURL = 'https://hello.iitk.ac.in/api/' + course + '/lectures/summary'
  data = json.loads(r.get(summaryURL, headers={
    'uid':cookies['uid'],
    'token':cookies['token'],
  }).content)
  # resourceURL = 'https://hello.iitk.ac.in/api/' + course + '/resources'
  # resourceData = json.loads(r.get(resourceURL, headers={
  #   'uid':cookies['uid'],
  #   'token':cookies['token'],
  # }).content)
  folder = re.sub(r'[\\\/:*?"<>|]',' - ', courseNames[course])
    ## Calculating Resources

  temp = []
  for res in data:
    toInsert = True
    for entry in temp:
      if entry['week'] == res['week']:
        entry['lectures'].append(res)
        toInsert = False
    if toInsert:
      temp.append({"week" : res['week'], 'lectures': [res]})
  for entry in temp:
    lecs = list(entry['lectures'])
    entry['lectures'] = []
    for lecture in lecs:
      topicExists = False
      for lec_2 in entry['lectures']:
        if lecture['topic'] == lec_2['topic']:
          topicExists = True
          lec_2['lectures'].append(lecture)
          break
      if topicExists == False:
        entry['lectures'].append({
          "topic": lecture['topic'],
          "lectures": list([lecture])
        })
  metadata, firstVideo = courseDirectoryMetadata(temp, minified=True)
  if firstVideo == None:
    print(folder)
    print('Fucked')
  else:
    firstVideo.insert(0, folder)
    FirstVideos.append(firstVideo)
  Parsed_Data[folder] = metadata

open('resources.js','w').write('const StudyResources={};'.format(json.dumps(Parsed_Data, sort_keys=True)))

import cv2
threshold = 100
os.makedirs(os.path.join('thumbs'), exist_ok=True)
for f in FirstVideos:
  vcap = cv2.VideoCapture(os.path.join(*f))
  res, im_ar = vcap.read()
  while im_ar.mean() < threshold and res:
      res, im_ar = vcap.read()
  im_ar = cv2.resize(im_ar, (480, 270), 0, 0, cv2.INTER_LINEAR)
  cv2.imwrite(os.path.join('thumbs', '{}.png'.format(f[0])), im_ar)
  res, thumb_buf = cv2.imencode('.png', im_ar)
  bt = thumb_buf.tobytes()

from distutils.dir_util import copy_tree
copy_tree(os.path.dirname(__file__) , os.getcwd())

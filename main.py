import asyncio
import os
import random
from datetime import datetime,timedelta
import pytz
import smtplib
import ssl
from email.message import EmailMessage
import os
from pyppeteer import launch
from dotenv import load_dotenv, find_dotenv
from bs4 import BeautifulSoup
from pymongo import MongoClient
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

load_dotenv()


def connectMongo():
    mongo_url = os.environ.get('mongouri')
    client = MongoClient(mongo_url,socketTimeoutMS=60000,maxIdleTimeMS=60000)
    db = client['TP']
    return db,client

def email(masterList,entity):
  db,client = connectMongo()
  collection = db.get_collection('emails')
  email_user = 'ninja.coolprojects@gmail.com'
  email_password = os.getenv('GMAIL_PASS')
  email_send = ''
  email_list = []
  for x in collection.find():
      email_list.append(x.get('email_id'))
      email_send += f'{x.get("email_id")},'
      
  email_send = email_send[:-1]
  for job in masterList:
    subject = job.get('company_name')
    msg = MIMEMultipart()
    msg['From'] = str(Header(f'NOTIFICATION <{email_user}>')) 
    msg['To'] = email_send
    msg['Subject'] = subject
    
    if entity == 'oportunity':
      obj = open('./opportunity.txt','r')
      html = obj.read()
      html=html.replace('"Company name"', job.get('company_name')).replace("Date-main",job.get('deadline'))
    else:
      obj = open('./notification.txt','r')
      html = obj.read()
      html=html.replace('[Company Name]', job.get('company_name')).replace("News/Result",job.get('type'))
        
    
    msg.attach(MIMEText(html, "html"))
    text = msg.as_string()
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context())
    server.login(email_user,email_password)
    server.sendmail(email_user,email_list,text)
    server.quit()
  if client is not None:
    client.close()

  
def job_notification(jobs,cur_date):
    try:
      db,client = connectMongo()
      collection = db.get_collection('jobs')
      obj={}
      for x in collection.find({'date':str(cur_date)},{'date':1,'count':1}):
          obj=x
      db_count = obj.get('count')
      if db_count is None:
          collection.insert_one({"count":len(jobs),"date":str(cur_date)})
          print(jobs)
          email(jobs,'oportunity')
          return
      number_of_jobs = len(jobs)
      if db_count == number_of_jobs:
          return
      
      if db_count<number_of_jobs:
          collection.update_one({'date':str(cur_date)},{"$set": {"count": number_of_jobs}})
          print(jobs)
          email(jobs[:number_of_jobs-db_count],'oportunity')
      
      client.close()
    
    except Exception as e:
      print(e)
    finally:
      if client is not None:
        client.close()
    
def todays_date():
    your_timezone = "Asia/Calcutta"
    current_utc_time = datetime.utcnow()
    your_timezone_obj = pytz.timezone(your_timezone)
    current_time_in_timezone = current_utc_time.replace(tzinfo=pytz.utc).astimezone(your_timezone_obj)
    today_date = current_time_in_timezone.date()  
    return today_date  

def parser(soup):
    # build jobs list 
    job_list = []
    jobs = soup.find(id='job-listings')
    if jobs:
        rows = jobs.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            cells = list(cells)
            if len(cells)<=0:
                continue
            cur = {}
            cur['company_name'] = cells[0].text
            cur['deadline'] = cells[1].text
            cur['posted_on'] = cells[2].text
            job_list.append(cur)
    
    cur_date = todays_date()-timedelta(days=0)
    todays_job = []
    for job in job_list:
        posted_date = job['posted_on']
        posted_date = datetime.strptime(posted_date,"%d/%m/%Y").strftime("%Y-%m-%d")
        if str(posted_date) == str(cur_date):
            todays_job.append(job)
    
    # build notification list
    notification_list = []
    notifications = soup.find(id='newseventsx')
    if notifications:
        rows = notifications.find_all('td')
        for row in rows:
            cells = row.find_all('h6')
            if cells:
                cur = {}
                cur['company_name'] = cells[0].text
                cells = row.find_all('i')
                type= cells[0].find_all('b')
                if len(type)>0:
                    type = type[0].text
                else:
                    temp = row.find_all('b')
                    type = temp[0].text
                cur['type'] = type
                cur['date_time']=cells[-1].text
                date_time = cells[-1].text
                if date_time:
                    day = []
                    for x in range(0,len(date_time)):
                        if date_time[x] == '-' or date_time[x] == '.':
                            day.append(x)
                    t = ''
                    t += date_time[day[0]-2:day[0]+8]

                    if '.' in t:
                        t = datetime.strptime(t,"%d.%m.%Y").strftime('%Y-%m-%d')
                    else:
                        t = datetime.strptime(t,"%d-%m-%Y").strftime('%Y-%m-%d')

                    if str(t)==str(todays_date()-timedelta(days=0)):
                        notification_list.append(cur)
                
        if len(notification_list)>0:
            notification(notification_list)  
    if len(todays_job)>0:
        job_notification(todays_job,cur_date) 

def notification(jobs):
  try:
    cur_date = todays_date()-timedelta(days=0)
    db,client = connectMongo()
    collection = db.get_collection('notifications')
    obj={}
    for x in collection.find({'date':str(cur_date)},{'date':1,'count':1}):
        obj=x
    db_count = obj.get('count')
    if db_count is None:
        collection.insert_one({"count":len(jobs),"date":str(cur_date)})
        print(jobs)
        email(jobs,'notification')
        return
    number_of_jobs = len(jobs)
    if db_count == number_of_jobs:
        return
    
    if db_count<number_of_jobs:
        collection.update_one({'date':str(cur_date)},{"$set": {"count": number_of_jobs}})
        print(jobs)
        email(jobs[:number_of_jobs-db_count],'notification')
    
    client.close()
  
  except Exception as e:
    print(e)
  finally:
    if client is not None:
      client.close()
    
    
def parseHtml(html):
    soup = BeautifulSoup(html,'html.parser')
    return soup

async def main():
    if os.environ.get('ENVIRONMENT') == 'PRODUCTION':
        browser = await launch()
        page = await browser.newPage()
        await page.goto('https://tp.bitmesra.co.in/login.html')
        state = random.randint(1,5)
        await page.type('#identity',os.environ.get(f'identity{state}'))
        await page.type('#password',os.environ.get(f'password{state}'))
        await page.click('.auth-form-btn')
        page2 = await browser.newPage()
        await page2.goto('https://tp.bitmesra.co.in/index.html')
        html = await page2.content()
        soup = parseHtml(html)
        await browser.close()
        parser(soup)
    else:
        Func = open("GFG-1.html","r")
        temp = Func.read()
        soup = parseHtml(temp)
        parser(soup)


asyncio.get_event_loop().run_until_complete(main()) # remove timedelta for production builds









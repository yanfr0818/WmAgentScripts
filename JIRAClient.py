import sys,os,json
import jira

class JIRAClient:
    def __init__(self, debug=False,cookie=None):
        self.server='https://its.cern.ch/jira'

        cookie = os.environ.get('JIRA_SSO_COOKIE', cookie)
        cookies = {}
        try:
            print "using cookie from", cookie
            for l in open(cookie,'r').read().split('\n'):
                try:
                    s = l.split()
                    if s[5] in ['JSESSIONID','atlassian.xsrf.token']:
                        cookies[ s[5] ] = s[6]
                except:
                    pass
        except:
            print cookie,"is not a file?"
            print "run cern-get-sso-cookie -u https://its.cern.ch/jira/loginCern.jsp -o jira.txt, or something like that"
        #print cookies
        if not cookies:
            print "That ain't going to work out"
            sys.exit(1)
        self.client = jira.JIRA('https://its.cern.ch/jira' , options = {'cookies':  cookies})
    
    def create(self , indications , do = True):
        fields = {
            'project' : 'CMSCOMPPR',
            'issuetype' : {'id' : "3"}
            }
        label = indications.get('label',None)
        who = {
            'WorkflowTrafficController' : 'sagarwal',
            'UnifiedOfficer' : 'sagarwal',
            'AgentDoc' : 'sagarwal'
        }.get(label,None)
           
        if label:
            fields['labels'] = [ label ]
        if who:
            fields['assignee'] = {'name':who,'key':who}
        summary = indications.get('summary',None)
        if summary:
            fields['summary'] = summary
        description = indications.get('description', None)
        if description:
            fields['description'] = description
        priority = indications.get('priority', None)
        print type(priority)
        if type(priority) == int:
            ## transform to a str
            #needs decision : 6
            #blocker : 1
            #critical : 2
            #major : 3
            #minor : 4

            prios = {
                0  : '4',
                85000  : '3',
                110000 : '2'
            }
            
            set_to = None
            for p in sorted(prios.keys()):
                if priority>p:
                    set_to = prios[p]
            priority = set_to

        elif not priority.isdigit():
            priority = { 'decision' : '6',
                         'blocker' : '1'}.get(priority, None)
        if priority:
            fields['priority'] = {'id' : priority}

        print fields
        if do:
            i = self.client.create_issue( fields) 
            return i

    def find(self ,specifications):
        query  = 'project=CMSCOMPPR'
        
        if specifications.get('prepid',None):
            query += ' AND summary~%s'%(specifications['prepid'])
        return self._find( query )

    def comment(self, key, comment):
        if not comment: return
        self.client.add_comment( key, comment )

    def _find(self, query):
        return self.client.search_issues( query )

    def get(self, jid):
        return self.client.issue( jid )

    def _transition(self, status, jid):
        to = {'closed' : '2',
              'reopened' : '3',
              'progress' : '4'
              }.get( status , None)
        if to:
            try:
                print jid,"to",status
                self.client.transition_issue( jid, to)
            except Exception as e:
                print "transition to",status,"not successful"
                print str(e)
        else:
            print "transition to",status,"not known"

    def progress(self, jid):
        self._transition('progress', jid)

    def reopen(self, jid):
        self._transition('reopened', jid)

    def close(self, jid):
        self._transition('closed', jid)

if __name__ == "__main__":
    JC = JIRAClient(cookie = 'jira.txt')
    
    i= JC.get('CMSCOMPPR-4516')
    print i.fields.summary

    ii = JC.find({'prepid' : 'SUS-RunIISummer16MiniAODv3-00261'})
    print [io.key for io in ii]

    JC.reopen('CMSCOMPPR-4518')
    JC.progress('CMSCOMPPR-4518')
    JC.close('CMSCOMPPR-4518')

    #JC.create( {
    #    'priority' : 120000,
    #    'summary' : 'automatic',
    #    'label' : 'WorkflowTrafficController',
    #    'description' : 'Automatic JIRA from unified'},
    #           do = False)

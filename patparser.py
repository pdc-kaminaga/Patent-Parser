from bs4 import BeautifulSoup
import urllib
import sys
import re

import patutil

'''tagList = [ 'patent-application-publication', # Enclosing tags
            'document-id>document-date', # Date (published?)
            'title-of-invention', # Title of invention
            'subdoc-abstract>paragraph', # Abstract
            'inventors', # List of inventors
            'subdoc-description>cross-reference-to-related-applications', # Cross reference to related applications
            'domestic-filing-data>application-number>doc-number', # Id number
            'domestic-filing-data>filing-date', # US Date filed
            # PCT Tags
            'foreign-priority-data>filing-date', # PCT Filing Date
            'foreign-priority-data>priority-application-number>doc-number', # PCT Application number

            'cross-reference-to-related-applications>paragraph', # Related Patent Documents
            'subdoc-description>federal-research-statement>paragraph-federal-research-statement', # Government Interest? - Paragraph acknowledging NSF
            'continuity-data>division-of' # Parent Case - cases in <parent-child>? 
            ]'''

class Tags():
    enclosing = ''
    pubdate = ''
    invtitle = ''
    abstract = ''
    inventors = ''
    crossref = ''
    appnum = ''
    appdate = ''
    pct_filedate = ''
    pct_filenum = ''
    pct_371cdate = ''
    pct_pubnum = ''
    pct_pubdate = ''
    relatedpub = ''
    relateddocs = ''
    govint = ''
    parentcase = ''
    
    def setTags(self, year):
        if year >= 07:
            # 2007 tagslist
            self.enclosing = 'us-patent-application'
            self.pubdate = 'publication-reference>document-id>date'
            self.invtitle = 'invention-title'
            self.abstract = 'abstract>p'
            self.inventors = 'applicants' #'us-parties>inventors'
            self.crossref = '<?cross-reference-to-related-applications description="Cross Reference To Related Applications" end="lead"?><?cross-reference-to-related-applications description="Cross Reference To Related Applications" end="tail"?>' #
            self.appnum = 'application-reference>document-id>doc-number'
            self.appdate = 'application-reference>document-id>date'
            self.pct_filedate = 'pct-or-regional-filing-data>document-id>date' #?
            self.pct_filenum = 'pct-or-regional-filing-data>document-id>doc-number' #?
            self.pct_371cdate = 'pct-or-regional-filing-data>us-371c124-date'
            self.pct_pubnum = 'pct-or-regional-publishing-data>document-id>doc-number' #?
            self.pct_pubdate = 'pct-or-regional-publishing-data>document-id>date' #?
            self.relatedpub = 'related-publication>document-id>doc-number'
            self.relateddocs = 'us-related-documents' #?
            self.govint = '<?federal-research-statement description="Federal Research Statement" end="lead"?><?federal-research-statement description="Federal Research Statement" end="tail"?>' #Govt interest?
            self.parentcase = 'us-related-documents>parent-doc>document-id>doc-number' #?
        
        if year >= 2012:
            # Figure this out
            pass
    
    def getTags(self, year):
        self.setTags(year)

        return [self.pubdate, self.invtitle, self.abstract, self.inventors, self.crossref, self.appnum, self.appdate, 
                self.pct_filedate, self.pct_filenum, self.pct_371cdate, self.pct_pubnum, self.pct_pubdate,
                self.relatedpub, self.relateddocs, self.govint, self.parentcase]
                            

xmldocs = [] # split_xml saves the split xml lists here 
xmliteration = 0 # Progression through xmldocs

# Will contain sets of the relevant scraped tags
datalists = []

file_writer = None

tags = Tags()

def getUrlList(url, sort=True):
    response = urllib.urlopen(url)
    soup = BeautifulSoup(response, ["lxml", "html"])
    result = []
    # Google downloading
    for link in soup.find_all('a'):
        if link.text.strip()[:3] == 'ipa' or link.text.strip()[:2] == 'pa':
            result.append(link.get('href'))
            #print 'Appending %s' % link.get('href')
    if sort: result = sorted(result, key=lambda str: re.sub('[^0-9]', '', str))
    return result 

# The parser will not parse past the second dtd statement, so this will split each xml segment into its own file in memory
def split_xml(fulldoc):
    xml = []
    lnum = 0
    n_iter = 0
    print 'Splitting xml, please wait...'
    
    found = False
    for line in fulldoc:
        lnum += 1
        xml.append(line)
        
        # Try and find where the tag changes so I can patch it in
        if line.strip().find(formatTag(tags.enclosing)) >= 0:
            found = True

        if (line.strip().find(formatTag(tags.enclosing, True)) >= 0):
            # Clone the list and append it to xmldocs
            xmldocs.append(list(xml))
            # Write to file (should be commmented out, for debugging purposes
            #f = open(getwd() + '/output.csv', 'a') 
            #f.write(''.join(xml))
            n_iter += 1
            xml = []
            sys.stdout.write("\rSplit %d on line %d ..." % (n_iter, lnum))
            sys.stdout.flush()
            if n_iter >= 254:
                break
            

    print 'Done with length %d.' % len(xmldocs)

def scrape_multi(year_):
    global year
    year = year_

    for xml in xmldocs:
        #Add data to datalist
        data = scrape(xml)
        datalists.append(data)
        global xmliteration
        xmliteration += 1
    # Add line return to output
    print ''


def scrape(xmllist):
    sys.stdout.write("\rScraping %s of %s." % (xmliteration + 1, len(xmldocs)))
    sys.stdout.flush()
    
    # Gets the government interest field and looks for NSF or national science foundation
    if (get_govt_interest(xmllist)):
        print 'Found NSF reference, adding to CSV. <!!!!!!!!!!!'
    else:
        return 
    # Create a string from the singular xml list created in split_xml()
    xml = '\n'.join(xmllist)
    soup = BeautifulSoup(xml, ["lxml", "xml"])

    # List all scraped data will be stored in
    datalist = []

    global tags
    for tag in tags.getTags(year):
        # Non bs4 parsing
        if (tag[0:2] == '<?'):
            # Split start and end tags
            split = tag.find('>') + 1
            tagpair = (tag[0:split], tag[split:])
            print tags
            datalist.append([tag, strfind_tag(tagpair[0], tagpair[1], xmllist)])
        else:
            datalist.append([tag, parse_xml(soup, tag)])

    return datalist


def get_govt_interest(xmllist):
    standardline = strfind_tag('<?federal-research-statement description="Federal Research Statement" end="lead"?>','<?federal-research-statement description="Federal Research Statement" end="tail"?>', xmllist)
    
    print 'Final text',standardline
    if standardline == None:
        return False

    standardline = re.sub("[^a-zA-Z0-9 ]", "", standardline).lower() # Remove non alphanumerics or spaces

    # Keep only alphanumerics/spaces when searching for the abbreviation, and only keep alphanumerics when searching for the full name
    if (standardline.find('nsf') >= 0 or re.sub('[ ]', '', standardline).find('nationalsciencefoundation') >= 0):
        return True

    return False



# get Govt Interest without using lxml (prevents a whole xml tree structure from needing to be parsed and created)
def strfind_tag(starttag, endtag, xmllist):
    opentag = False
    result = ''
    for line in xmllist:
        startpos = line.find(starttag)
        endpos = line.find(endtag)
        if startpos >= 0:
            opentag = True

        if opentag == True:           
            text = line
            # If the start or end pos is on the current line, only look at the portion of the line within the tags
            if startpos >= 0: 
                text = text[startpos:]
            if endpos >= 0: 
                # Get substring within tag (subtract startpos in order to remove the offset introduced above
                text = text[: endpos]
            
            result += text
            #print 'Result "%s", startpos %s, endpos %s' % (text, startpos, endpos)

        if endpos >= 0:
            return result[len(starttag) : ]
    return 'None'


def parse_xml(soup, tag):
    global tags
    finaltag = None #The tag object which will be printed or returned at the end of the scrape
    result = 'None'
    print '=======Now searching tag', tag + '======='
     
    # (Re)sets subsoup to the top of the xml tree
    print tags
    subsoup = soup.find(tags.enclosing)
    tagtree = tag.split('>')
    #print 'tagtree length:', len(tagtree)
    for i in xrange(0, len(tagtree)):
        if subsoup == None:
            #print 'WARNING: \'' + tagtree[i - 1] + '\' is none in tag tree:', ', '.join(tagtree)
            result = 'None'
            break

        elif i < len(tagtree) - 1: # If not at the end of the tree
            subsoup = subsoup.find(tagtree[i])

        else: # If at the end of the tree (or if the tree only has one element)
            finaltag = subsoup.find(tagtree[i])
            result = tagString(finaltag)

            # Add special formatting for inventors tag
            if tag == 'applicants':
                templist = []
                if finaltag != None:
                    for name in finaltag.find_all('addressbook'):
                        #print name
                        templist.append('[')
                        i = 0
                        # Only append if tag contains name (first-name), (last-name), etc.
                        # Iterative
                        '''for namepart in name.children:
                            if str(type(namepart)) == '<class \'bs4.element.Tag\'>' and namepart.name.find('name') >= 0:
                                print namepart, str(type(namepart))
                                # Append all strings
                                if i > 0:
                                    templist.append(' ')
                                print 'Appending' + namepart.string
                                templist.append(namepart.string.strip())
                                i += 1'''
                        # Hard coded
                        templist.append(name.find('first-name').string)
                        if (name.find('middle-name') != None):
                            templist.append(' ' + name.find('middle-name').string)
                        templist.append(' ' + name.find('last-name').string)
                            
                        templist.append(']')
                
                    result = ''.join(templist)

    print type(result), result
    return unicode(result)


# Put in own method to make logic less cluttered
def tag_name_contains(descend, string):
    return descend != None and str(type(descend)) == '<class \'bs4.element.Tag\'>' and descend.name != None and descend.name.find(string) != -1


def formatTag(tag, close=False):
    # Remove the tag tree data from the string and enclose it in <>, with an optional /
    return  ('</' if close else '<') + tag[ tag.rfind('>') + 1: ] + '>'


def tagString(tag):
    result = ''
    if (tag == None):
        result = 'None'
    elif (tag.string == None):
         result = tag.get_text(' ')
    else:
        result = tag.string 
    return result


def tagTreeString(tag):
    tree = ''
    if tag == None or tag.parents == None:
        return 'None'
    for parenttag in tag.parents:
        if (parenttag.name != None):
            tree = '<' + parenttag.name + '> ' + tree
    return tree

if __name__ == '__main__':
    print 'This is not runnable code.'

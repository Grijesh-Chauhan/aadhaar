""" Wrapper over Python's requests library. """
from socket import error as SocketError
import requests, cgi, errno, os, urlparse
from BeautifulSoup import BeautifulSoup
from PIL import Image
from StringIO import StringIO

from requests_toolbelt import MultipartEncoder

CONNECTION_ABORTED = "Connection aborted. Try again later."
REQUEST_FAILED = "Request failed. Try again later."
INVALID_REQUEST = "Invalid request. Try again."
CONNECTION_ECONNRESET = ("Remote system could not complete request. "
                         "Please try after some time."
                        )
JASON_DECODING_FAILURE = ("Remote system has encountered some technical problem. "
                          "Please try after some time."
                          )

class WebAPIException(Exception):
    # always catch this exception and you can return except message
    # to front end with some suitable http error status
    def __init__(self, msg, *args, **kwargs):
        super(WebAPIException, self).__init__(msg, *args, **kwargs)
        if isinstance(msg, dict):
            self.dict = msg
        else:
            self.dict = { 'error': msg }
            
    def __str__(self):
        return str(self.dict)
    
class WebAPI(object):
    """ WebAPI class can be used to simulate web-Form interface as Python API """
    
    ITER_CHUNK_SIZE = 1024
    
    def __init__(self, headers, cookies=None):
        self.session = requests.session()
        if headers:
            self.session.headers.update(headers)
        self.cookies = cookies
        
    @classmethod
    def is_success(cls, code):
        return code >= 200 and code <= 299
        
    def update_cookies(self):
        # may be more apt would be to do response.cookies.get_dict()
        cookies = self.session.cookies.get_dict()
        if cookies:
            if self.cookies:
                self.cookies.update(cookies)
            else:
                self.cookies = cookies
        
    def get(self, url, stream=None, **kwargs):
        try:
            kwargs.pop('cookies', None)
            response = self.session.get(url, cookies=self.cookies, stream=stream, **kwargs)
        except requests.ConnectionError as e:
            # occurs when DNS req fails, timeouts etcs, network not found
            raise WebAPIException(CONNECTION_ABORTED)
        except SocketError as e:
            if e.errno == errno.ECONNRESET:
                raise WebAPIException(CONNECTION_ECONNRESET)
            raise e
        if not self.is_success(response.status_code):
            raise WebAPIException(REQUEST_FAILED)
        self.update_cookies()
        return response
        
    def get_file(self, url, stream=True, **kwargs):
        """
        returns filename and *content
        if stream is True then returns iterator of content, default stream is True 
        """
        # downloads file by http get call
        response = self.get(url, stream=stream, **kwargs)
        try:
            params = cgi.parse_header(response.headers['content-disposition'])[1]
            filename = params["filename"]
        except (KeyError, IndexError) as e:
            # get filename from url of response
            path = urlparse.urlparse(response.url).path
            filename = os.path.basename(path).strip() or None
            if filename and not isinstance(filename, unicode):
                filename = unicode(filename, 'utf-8')
        if stream:
            return filename, response.iter_content(WebAPI.ITER_CHUNK_SIZE)
        return filename, response.content
            
    def post(self, url, data, **kwargs):
        try:
            response = self.session.post(url, data, cookies=self.cookies, **kwargs)
        except requests.ConnectionError as e:
            raise WebAPIException(CONNECTION_ABORTED)
        except SocketError as e:
            if e.errno == errno.ECONNRESET:
                raise WebAPIException(CONNECTION_ECONNRESET)
            raise e            
        if not self.is_success(response.status_code):
            raise WebAPIException(REQUEST_FAILED)
        self.update_cookies()
        return response
        
    def put(self, url, data=None, **kwargs):
        try:
            kwargs.pop('cookies', None)
            response = self.session.put(url, data=data, cookies=self.cookies, **kwargs)
        except requests.ConnectionError as e:
            raise WebAPIException(CONNECTION_ABORTED)
        except SocketError as e:
            if e.errno == errno.ECONNRESET:
                raise WebAPIException(CONNECTION_ECONNRESET)
            raise e
        if not self.is_success(response.status_code):
            raise WebAPIException(REQUEST_FAILED)
        self.update_cookies()
        return response
        
    def validate(self):
        """ this method should be overriden """
        pass
        
    def parse(self, beautiful_html):
        """ page specific parsing routine should be implemented by derived class
            which return result in required format. The default implementation
            returns `beautiful_html` - an instance of BeautifulSoup.
        """
        return beautiful_html
        
    def beautifulsoup(self, html):
        return BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES)
        
    def webpost(self, url, data, **kwargs):
        """ calls self.validate() followed by self.parse(). Returns results parsed by
            self.parse() on error raise webrequests.WebAPIException
        """
        self.validate()
        response = self.post(url, data, **kwargs)
        return self.parse(self.beautifulsoup(response.content))
        
    def webget(self, url, **kwargs):
        """ a wrapper over get() that do NOT call any validator and parse method
            but returns BeautifulSoup instance do be utilize for parse useful
            informations.
        """
        return self.beautifulsoup(self.get(url, **kwargs).content)

    def ajaxget(self, url, **kwargs):
        """ makes ajax call and return decoded JSON dict """
        # any dictionaries that you pass to a request method will be merged with
        # the session-level values that are set. The method-level parameters 
        # override session parameters. Note, however, that method-level parameters
        # will not be persisted across requests, even if using a session.
        response = self.get(url=url,
                            headers={'X-Requested-With': 'XMLHttpRequest'},
                            **kwargs
                           )
        try:
            return response.json()
        except ValueError as decodingerror:
            raise WebAPIException(JASON_DECODING_FAILURE)
        
    def ajaxpost(self, url, data=None, **kwargs):
        self.validate()
        response = self.post(url=url, data=data or {},
                             headers={'X-Requested-With': 'XMLHttpRequest'},
                             **kwargs
                            )
        content_type = cgi.parse_header(response.headers['Content-Type'])[0]
        if 'html' in content_type:
            return self.parse(self.beautifulsoup(response.content))
        if 'json' in content_type:
            try:
                return response.json()
            except ValueError as decodingerror:
                raise WebAPIException(JASON_DECODING_FAILURE)
        return response # or we should rise error
        
    def ajaxput(self, url, data=None, **kwargs):
        self.validate()
        response = self.put(url=url, data=data or {},
                            headers={'X-Requested-With': 'XMLHttpRequest'},
                            **kwargs
                           )
        content_type = cgi.parse_header(response.headers['Content-Type'])[0]
        if 'html' in content_type:
            return self.parse(self.beautifulsoup(response.content))
        if 'json' in content_type:
            try:
                return response.json()
            except ValueError as decodingerror:
                raise WebAPIException(JASON_DECODING_FAILURE)
        return response # or we should rise error
        
    def multipart_upload(self, url, data=None, **kwargs):
        self.validate()
        encoder = MultipartEncoder(fields=data)
        response = self.post(url=url, data=encoder,
                             headers={'Content-Type': encoder.content_type,
                                      'Content-Length': encoder.len,
                                     },
                             **kwargs
                            )
        return self.parse(self.beautifulsoup(response.content))
                
    def show_captcha(self, url):
        """ debugging purpose: retrives and show captcha """
        _, content_iterator = self.get_file(url)
        imagebytes = bytes().join(content_iterator)
        in_memory_file = StringIO(imagebytes)
        Image.open(in_memory_file).show()

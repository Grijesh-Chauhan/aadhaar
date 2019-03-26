import re
import urlparse
import datetime

import webrequests
from utils import add_url_params, parse_query_paras

class UidaiWebAPI(webrequests.WebAPI):
    """ Unique Identification Authority of India """
    
    URL_SCHEME = "https://"
    HOST = "resident.uidai.gov.in"
    HEADERS = {
     'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
     'Accept-Encoding': "gzip, deflate, sdch",
     'Accept-Language': "en-US,en;q=0.8",
     'Connection': "keep-alive",
     'Host': HOST,
     'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.86 Safari/537.36",
    }
    BASE_URL = URL_SCHEME + HOST
    
    def __init__(self, *args, **kwargs):
        super(UidaiWebAPI, self).__init__(headers=UidaiWebAPI.HEADERS, *args, **kwargs)
        
class CaptchaGetAPI(UidaiWebAPI):

    is4digits = re.compile(r"[0-9]{4}").search

    def __init__(self, captcha_code=None, *args, **kwargs):
        self.captcha_code = captcha_code
        super(CaptchaGetAPI, self).__init__(*args, **kwargs)            
    
    PARAMS = {
        'p_p_cacheability': 'cacheLevelPage',
        'p_p_col_count': '1',
        'p_p_col_id': 'column-1',
        'p_p_id': 'aadhaarverification_WAR_AadhaarVerificationportlet',
        'p_p_lifecycle': '2',
        'p_p_mode': 'view',
        'p_p_resource_id': 'captchaImage',
        'p_p_state': 'normal'
    }

    def get_captcha_url(self, update=False):
        """ """
        url = self.get_url('get')
        if update:
            miliseconds = datetime.datetime.now().microsecond % 1000
            params = dict(CaptchaGetAPI.PARAMS, force=miliseconds)
        params = CaptchaGetAPI.PARAMS
        return add_url_params(url, params)
        
    def get_captcha(self):
        """
        can be used to wrap into download file APIs
        """
        # captcha images and audio files are very small so streaming not required
        _, content = self.get_file(self.get_captcha_url(), stream=False)
        return content
        
    def show_captcha(self):
        """ debugging purpose: retrives and show captcha """
        super(CaptchaGetAPI, self).show_captcha(url=self.get_captcha_url())
        
    def validate_captcha_code(self):
        if not self.captcha_code:
            raise webrequests.WebAPIException({
                'captcha_code': "Please Enter Captcha."
            })
        
        if (not self.is4digits(self.captcha_code)) or len(set(self.captcha_code)) < 2:
            raise webrequests.WebAPIException({
                'captcha_code': "Please Enter Valid Captcha."
            })


class AdharVerificationAPI(CaptchaGetAPI):
    """
    >> webapi = AdharVerificationAPI()
    >> webapi.adhar = "442837314297"
    >> webapi.show_captcha() # display a image
    >> webapi.captcha_code = "2927"  # enter captcha from image
    >> webapi.verify()
    {u'Age Band :': u'30-40',
     u'Gender :': u'MALE',
     u'Mobile Number :': u'xxxxxxx520',
     u'State :': u'Delhi',
     'adhar': '442837314297'}
    """

    is12digits = re.compile(r"[0-9]{12}").search

    def __init__(self, adhar=None, captcha_code=None, *args, **kwargs):
        self.adhar = adhar
        super(AdharVerificationAPI, self).__init__(captcha_code=captcha_code, 
                                                             *args, **kwargs)
    
    @classmethod
    def get_url(cls, action='get'):
        action = action.lower()
        if action == 'post':
            relative_url = "aadhaarverification"
        elif action == 'get':
            relative_url = "aadhaarverification"
        else:
            raise ItdWebAPIException(webrequests.INVALID_REQUEST)
        return urlparse.urljoin(cls.BASE_URL, relative_url)
        
    def get_hidden_data(self):
        beautiful_html = self.webget(self.get_url('get'))
        form = beautiful_html.find('form', { 'id': '_aadhaarverification_WAR_AadhaarVerificationportlet_AadhaarVerificationForm' })
        self._params = parse_query_paras(form['action'])
        inputs = { input.get('name') or "": input.get('value') or "" 
                   for input in form.findAll('input') 
                 }
        inputs.pop('Verify', None)
        return inputs

    def data(self):
        data = self.get_hidden_data()
        data['_aadhaarverification_WAR_AadhaarVerificationportlet_captchaText'] = self.captcha_code
        data['uid'] = self.adhar
        return data
        
    def params(self):
        return self._params
        
    def validate_adhar(self):
        if not self.adhar:
            raise webrequests.WebAPIException({
                'adhar': "Please Enter Captcha."
            })
        
        if (not self.is12digits(self.adhar)) or len(set(self.adhar)) < 2:
            raise webrequests.WebAPIException({
                'adhar': "Please Enter Valid Captcha."
            })
        
    def validate(self):
        self.validate_adhar()
        self.validate_captcha_code()
        
    def parse(self, beautiful_html):
        self._beautiful_html = beautiful_html
        error = beautiful_html.find('div', {'class': "portlet-msg-error"})
        if error:
            raise webrequests.WebAPIException({'captcha_code': error.text})
        message = beautiful_html.findAll('h2')[1].text
        if "doesn't" in message:
            raise webrequests.WebAPIException({'adhar': message})
        idivs = iter(beautiful_html.findAll('div', {'class': "floatLeft"}))
        values = {div.text: idivs.next().text for div in idivs}
        values['adhar'] = self.adhar
        return values
            
    def verify(self):
        return self.webpost(self.get_url('post'), data=self.data(), params=self.params())

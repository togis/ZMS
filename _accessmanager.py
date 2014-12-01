################################################################################
# _accessmanager.py
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
################################################################################

# Imports.
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.userfolder import UserFolder
from types import StringTypes
import copy
import sys
import time
import urllib
import zExceptions
# Product Imports.
import _confmanager
import _globals

# ------------------------------------------------------------------------------
#  _accessmanager.updateVersion:
# ------------------------------------------------------------------------------
def updateVersion(root):
  if not root.REQUEST.get('_accessmanager_updateVersion',False):
    root.REQUEST.set('_accessmanager_updateVersion',True)
    if root.getConfProperty('ZMS.security.build',0) == 0:
      root.setConfProperty('ZMS.security.build',1)
      userDefs = {} 
      def visit(docelmnt):
        d = docelmnt.getConfProperty('ZMS.security.users',{})
        for name in d.keys():
          value = d[name]
          userDef = userDefs.get(name)
          if userDef is None:
            userDef = {'nodes':{}}
            for key in value.keys():
              if not userDef.has_key(key):
                userDef[key] = value[key]
          nodes = value.get('nodes',{})
          for nodekey in nodes.keys():
            node = docelmnt.getLinkObj(nodekey)
            if node is not None:
              newkey = root.getRefObjPath(node)
              userDef['nodes'][newkey] = nodes[nodekey]
          userDefs[name] = userDef
        docelmnt.delConfProperty('ZMS.security.users')
        for client in docelmnt.getPortalClients():
          visit(client)
      visit(root)
      root.setConfProperty('ZMS.security.users',userDefs)

# ------------------------------------------------------------------------------
#  _accessmanager.user_folder_meta_types:
#
#  User Folder Meta-Types.
# ------------------------------------------------------------------------------
user_folder_meta_types = ['LDAPUserFolder','User Folder','Simple User Folder','Pluggable Auth Service']

# ------------------------------------------------------------------------------
#  _accessmanager.role_defs:
#
#  Role Definitions.
# ------------------------------------------------------------------------------
role_defs = {
   'ZMSAdministrator':['*']
  ,'ZMSEditor':['Access contents information','Add ZMSs','Add Documents, Images, and Files','Copy or Move','Delete objects','Manage properties','Use Database Methods','View','ZMS Author']
  ,'ZMSAuthor':['Access contents information','Add ZMSs','Copy or Move','Delete objects','Use Database Methods','View','ZMS Author']
  ,'ZMSSubscriber':['Access contents information','View']
  ,'ZMSUserAdministrator':['Access contents information','View','ZMS UserAdministrator']
}

# ------------------------------------------------------------------------------
#  _accessmanager.getUserId:
# ------------------------------------------------------------------------------
def getUserId(user):
  if type(user) is dict:
    user = user['name']
  elif user is not None and type(user) not in StringTypes:
    user = user.getId()
  return user

# ------------------------------------------------------------------------------
#  _accessmanager.role_permissions:
#
#  Role Permissions.
# ------------------------------------------------------------------------------
def role_permissions(self, role):
  permissions = map(lambda x: x['name'],self.permissionsOfRole('Manager'))
  if role_defs.has_key(role):
    role_def = role_defs[role]
    if '*' not in role_def:
      permissions = role_def
  return permissions

# ------------------------------------------------------------------------------
#  _accessmanager.updateUserPassword:
# ------------------------------------------------------------------------------
def updateUserPassword(self, user, password, confirm):
  if password!='******':
    if password != confirm:
      raise zExceptions.InternalError("Passwort <> Confirm")
    userFldr = user['localUserFldr']
    id = user['user_id_']
    if userFldr.meta_type == 'User Folder':
      roles = userFldr.getUser(id).getRoles()
      domains = userFldr.getUser(id).getDomains()
      userFldr.userFolderEditUser(id, password, roles, domains)
    elif userFldr.meta_type == 'Pluggable Auth Service' and user['plugin'].meta_type == 'ZODB User Manager':
      user['plugin'].updateUserPassword(id, password)
    return True
  return False

# ------------------------------------------------------------------------------
#  _accessmanager.setLocalRoles:
# ------------------------------------------------------------------------------
def setLocalRoles(self, id, roles=[]):
  filtered_roles = filter(lambda x: x in self.valid_roles(),roles)
  if len(filtered_roles) > 0:
    self.manage_setLocalRoles(id,filtered_roles)
  if self.meta_type == 'ZMS':
    home = self.aq_parent
    setLocalRoles(home,id,roles)

# ------------------------------------------------------------------------------
#  _accessmanager.delLocalRoles:
# ------------------------------------------------------------------------------
def delLocalRoles(self, id):
  self.manage_delLocalRoles(userids=[id])
  if self.meta_type == 'ZMS':
    home = self.aq_parent
    delLocalRoles(home,id)

# ------------------------------------------------------------------------------
#  _accessmanager.deleteUser:
# ------------------------------------------------------------------------------
def deleteUser(self, id):
  
  # Delete local roles in node.
  nodes = self.getUserAttr(id,'nodes',{})
  for node in nodes.keys():
    ob = self.getLinkObj(node)
    if ob is not None:
      user_id = self.getUserAttr(id,'user_id_',id)
      delLocalRoles(ob,user_id)
  
  # Delete user from ZMS dictionary.
  self.delUserAttr(id)

# ------------------------------------------------------------------------------
#  _accessmanager.UserFolderIAddUserPluginWrapper:
# ------------------------------------------------------------------------------
class UserFolderIAddUserPluginWrapper:

  def __init__(self, userFldr):
    self.userFldr = userFldr
    self.id = userFldr.id
    self.meta_type = userFldr.meta_type
    self.icon = userFldr.icon

  absolute_url__roles__ = None
  def absolute_url( self):
    return self.userFldr.absolute_url()
  
  def doAddUser( self, login, password ):
    roles =  []
    domains =  []
    self.userFldr.userFolderAddUser(login,password,roles,domains)
  
  def removeUser( self, login):
    self.userFldr.userFolderDelUsers([login])


################################################################################
################################################################################
###
###   Class AccessableObject
###
################################################################################
################################################################################
class AccessableObject: 

    # --------------------------------------------------------------------------
    #  AccessableObject.getUsers:
    # --------------------------------------------------------------------------
    def getUsers(self, REQUEST=None):
      users = {}
      d = self.getSecurityUsers()
      for user in d.keys():
        roles = self.getUserRoles( user, aq_parent=0)
        langs = self.getUserLangs( user, aq_parent=0)
        if len(roles) > 0 and len( langs) > 0:
          users[ user] = {'roles':roles,'langs':langs}
      return users

    # --------------------------------------------------------------------------
    #  AccessableObject.hasAccess:
    # --------------------------------------------------------------------------
    def hasAccess(self, REQUEST):
      auth_user = REQUEST.get('AUTHENTICATED_USER')
      access = auth_user.has_permission( 'View', self) in [ 1, True]
      if not access:
        access = access or self.hasPublicAccess() 
      return access

    # --------------------------------------------------------------------------
    #  AccessableObject.getUserRoles:
    # --------------------------------------------------------------------------
    def getUserRoles(self, userObj, aq_parent=1):
      roles = []
      try:
        roles.extend(list(userObj.getRolesInContext(self)))
        if 'Manager' in roles:
          roles = self.concat_list(roles,['ZMSAdministrator','ZMSEditor','ZMSAuthor','ZMSSubscriber','ZMSUserAdministrator'])
      except:
        pass
      nodes = self.getUserAttr(userObj,'nodes',{})
      ob = self
      depth = 0
      while ob is not None:
        if depth > sys.getrecursionlimit():
          raise zExceptions.InternalError("Maximum recursion depth exceeded")
        depth = depth + 1
        nodekey = self.getRefObjPath(ob)
        if nodekey in nodes.keys():
          roles = self.concat_list(roles,nodes[nodekey]['roles'])
          break
        if aq_parent:
          ob = ob.getParentNode()
        else:
          ob = None
      # Resolve security_roles.
      security_roles = self.getConfProperty('ZMS.security.roles',{})
      for id in filter(lambda x: x in security_roles.keys(),roles):
        dict = security_roles.get(id,{})
        for v in dict.values():
          for role in map(lambda x: x.replace( ' ', ''),v.get('roles',[])):
            if role not in roles:
              roles.append( role)
      return roles

    # --------------------------------------------------------------------------
    #  AccessableObject.getUserLangs:
    # --------------------------------------------------------------------------
    def getUserLangs(self, userObj, aq_parent=1):
      langs = []
      try:
        langs.extend(list(getattr(userObj,'langs',['*'])))
      except:
        pass
      nodes = self.getUserAttr(userObj, 'nodes', {})
      ob = self
      depth = 0
      while ob is not None:
        if depth > sys.getrecursionlimit():
          raise zExceptions.InternalError("Maximum recursion depth exceeded")
        depth = depth + 1
        nodekey = self.getRefObjPath(ob)
        if nodekey in nodes.keys():
          langs = nodes[nodekey]['langs']
          break
        if aq_parent:
          ob = ob.getParentNode()
        else:
          ob = None
      return langs


    ############################################################################
    ###
    ###  Public Access (Subscribers)
    ###
    ############################################################################

    # --------------------------------------------------------------------------
    #  AccessableObject.hasRestrictedAccess:
    # --------------------------------------------------------------------------
    def hasRestrictedAccess(self):
      restricted = False
      if 'attr_dc_accessrights_restricted' in self.getMetaobjAttrIds(self.meta_id):
        restricted = restricted or self.attr( 'attr_dc_accessrights_restricted') in [ 1, True]
      return restricted

    # --------------------------------------------------------------------------
    #  AccessableObject.hasPublicAccess:
    # --------------------------------------------------------------------------
    def hasPublicAccess(self):
      public = True
      if 'attr_dc_accessrights_public' in self.getMetaobjAttrIds(self.meta_id):
        public = public and self.attr( 'attr_dc_accessrights_public') in [ 1, True]
      if not public:
        return public
      nodelist = self.breadcrumbs_obj_path()
      nodelist.reverse()
      for node in nodelist:
        f = getattr(node,'hasRestrictedAccess',None)
        if f is not None:
          public = public and not f()
          if not public:
            return public
      return public


    # --------------------------------------------------------------------------
    #  AccessableObject.synchronizePublicAccess:
    # --------------------------------------------------------------------------
    def synchronizePublicAccess(self):
      # This is ugly, but necessary since ZMSObject is inherited from 
      # AccessableObject and ZMSContainerObject is inherited from 
      # AccessableContainer!
      restricted = self.hasRestrictedAccess()
      if self is not None and self.meta_type == 'ZMSLinkElement' and self.isEmbedded( self.REQUEST):
        ob = self.getRefObj()
        if ob is not None:
          for item in ob.breadcrumbs_obj_path():
            restricted = restricted or item.hasRestrictedAccess()
            if restricted: 
              break
      else:
        ob = self
      if isinstance( ob, AccessableContainer):
        if restricted:
          self.revokePublicAccess()
        else:
          self.grantPublicAccess()
      

    ############################################################################
    ###
    ###  Properties
    ###
    ############################################################################

    ############################################################################
    #  AccessableObject.manage_user:
    #
    #  Change user.
    ############################################################################
    manage_userForm = PageTemplateFile('zpt/ZMS/manage_user', globals())
    def manage_user(self, btn, lang, REQUEST, RESPONSE):
      """ AccessManager.manage_user """
      message = ''
      
      # Change.
      # -------
      if btn == self.getZMILangStr('BTN_SAVE'):
        id = getUserId(REQUEST['AUTHENTICATED_USER'])
        user = self.findUser(id)
        password = REQUEST.get('password','******')
        confirm = REQUEST.get('confirm','')
        if updateUserPassword(self,user,password,confirm):
          self.setUserAttr(id,'forceChangePassword',0)
          message += self.getZMILangStr('ATTR_PASSWORD') + ': '
        self.setUserAttr(user,'email',REQUEST.get('email','').strip())
        #-- Assemble message.
        message += self.getZMILangStr('MSG_CHANGED')
      
      # Return with message.
      if RESPONSE:
        message = urllib.quote(message)
        return RESPONSE.redirect('manage_main?lang=%s&manage_tabs_message=%s'%(lang,message))


################################################################################
################################################################################
###
###   Class AccessableContainer
###
################################################################################
################################################################################
class AccessableContainer(AccessableObject): 

    # --------------------------------------------------------------------------
    #  AccessableContainer.synchronizeRolesAccess:
    # --------------------------------------------------------------------------
    def synchronizeRolesAccess(self):
      message = []
      security_roles = self.getConfProperty('ZMS.security.roles',{})
      for id in security_roles.keys():
        self.manage_role(role_to_manage=id,permissions=[])
        message.append("id="+id)
        d = security_roles.get(id,{})
        for node in d.keys():
          message.append("node="+node)
          ob = self.getLinkObj(node)
          if ob is not None:
            message.append("ob="+ob.absolute_url())
            roles = d[node]['roles']
            message.append("roles="+str(roles))
            permissions = []
            for role in roles:
              permissions = ob.concat_list(permissions,role_permissions(self,role.replace(' ','')))
            message.append("permissions="+str(permissions))
            ob.manage_role(role_to_manage=id,permissions=permissions)
      return '\n'.join(message)


    # --------------------------------------------------------------------------
    #  AccessableContainer.restrictAccess:
    # --------------------------------------------------------------------------
    def restrictAccess(self):
      for lang in self.getLangIds():
        for key in ['index_%s.html','index_print_%s.html','search_%s.html','sitemap_%s.html']:
          id = key%lang
          if hasattr(self,id):
            ob = getattr(self,id)
            ob.manage_acquiredPermissions(permissions=['Access contents information','View'])
            for role in ['Manager']: 
              ob.manage_role(role_to_manage=role,permissions=role_permissions(ob,role))

    # --------------------------------------------------------------------------
    #  AccessableContainer.grantPublicAccess:
    # --------------------------------------------------------------------------
    def grantPublicAccess(self):
      self.restrictAccess()
      self.manage_acquiredPermissions(role_permissions(self,'Manager'))
      security_roles = self.getConfProperty('ZMS.security.roles',{})
      for role in filter(lambda x: x not in ['Anonymous','Authenticated','Owner','Manager',],self.valid_roles()):
        permissions = []
        if self.getLevel() == 0:
          permissions = role_permissions(self,role)
        self.manage_role(role_to_manage=role,permissions=permissions)
      # Anonymous / Authenticated.
      permissions = []
      if self.getLevel() == 0:
        permissions = ['Access contents information','View']
      self.manage_role(role_to_manage='Anonymous',permissions=permissions)
      self.manage_role(role_to_manage='Authenticated',permissions=permissions)

    # --------------------------------------------------------------------------
    #  AccessableContainer.revokePublicAccess:
    # --------------------------------------------------------------------------
    def revokePublicAccess(self):
      self.restrictAccess()
      self.manage_acquiredPermissions([])
      security_roles = self.getConfProperty('ZMS.security.roles',{})
      for role in filter(lambda x: x not in ['Anonymous','Authenticated','Owner','Manager',],self.valid_roles()):
        permissions=role_permissions(self,role)
        if role in security_roles.keys():
          permissions = []
          # Authors & Editors
          if len(permissions) == 0:
            ob = self.getParentNode()
            while ob is not None and len(permissions)==0:
              permissions = map(lambda x: x['name'], filter(lambda x: x['selected']=='SELECTED',ob.permissionsOfRole(role)))
              ob = ob.getParentNode()
          # Subscribers
          if len(permissions) == 0:
            security_role = security_roles[role]
            for node in security_role.keys():
              ob = self.getLinkObj(node)
              if ob == self:
                for node_role in security_role[node]['roles']:
                  node_role_id = node_role.replace(' ','')
                  node_role_permissions = role_permissions(self,node_role_id)
                  permissions = self.concat_list(permissions,node_role_permissions)
        self.manage_role(role_to_manage=role,permissions=permissions)
      # Anonymous / Authenticated.
      permissions=['Access contents information']
      self.manage_role(role_to_manage='Anonymous',permissions=permissions)
      self.manage_role(role_to_manage='Authenticated',permissions=permissions)


################################################################################
################################################################################
###
###   Class AccessManager
###
################################################################################
################################################################################
class AccessManager(AccessableContainer): 

    # --------------------------------------------------------------------------
    #  AccessManager.getRoleName
    # --------------------------------------------------------------------------
    def getRoleName(self, role):
      langKey = 'ROLE_%s'%role.upper()
      langStr = self.getZMILangStr(langKey)
      if langKey == langStr:
        return role
      return langStr

    # --------------------------------------------------------------------------
    #  AccessManager.getSecurityUsers:
    # --------------------------------------------------------------------------
    def getSecurityUsers(self):
      userDefs = {}
      root = self.breadcrumbs_obj_path()[0]
      d = root.getConfProperty('ZMS.security.users',{})
      if root == self:
        userDefs = copy.deepcopy(d)
      else:
        prefix = root.getRefObjPath(self)[:-2]
        for name in d.keys():
          value = d[name]
          nodes = value.get('nodes',{})
          nodekeys = filter(lambda x:x.startswith(prefix), nodes.keys())
          if len(nodekeys) > 0:
            userDef = {'nodes':{}}
            for key in value.keys():
              if not userDef.has_key(key):
                userDef[key] = value[key]
            for nodekey in nodekeys:
              userDef['nodes'][nodekey] = nodes[nodekey]
            userDefs[name] = userDef
      return userDefs

    # --------------------------------------------------------------------------
    #  AccessManager.searchUsers:
    # --------------------------------------------------------------------------
    def searchUsers(self, search_term=''):
      users = []
      if search_term != '':
        userFldr = self.getUserFolder()
        doc_elmnts = userFldr.aq_parent.objectValues(['ZMS'])
        if doc_elmnts:
          if userFldr.meta_type == 'LDAPUserFolder':
            login_attr = self.getConfProperty('LDAPUserFolder.login_attr',userFldr.getProperty('_login_attr'))
            users.extend(map(lambda x:x[login_attr],userFldr.findUser(search_param=login_attr,search_term=search_term)))
          elif userFldr.meta_type == 'Pluggable Auth Service':
            users.extend(map(lambda x:x['login'],userFldr.searchUsers(login=search_term,id=None,exact_match=True)))
          else:
            login_attr = 'login'
            users.extend(filter(lambda x: x==search_term,userFldr.getUserNames()))
      return users
  
  
    # --------------------------------------------------------------------------
    #  AccessManager.getValidUserids:
    # --------------------------------------------------------------------------
    def getValidUserids(self, search_term='', without_node_check=True, exact_match=False):
      encoding = self.getConfProperty('LDAPUserFolder.encoding','latin-1')
      local_userFldr = self.getUserFolder()
      columns = None
      records = []
      c = [{'id':'name','name':'Name'}]
      userFldr = self.getUserFolder()
      users = []
      if userFldr.meta_type == 'LDAPUserFolder':
        if search_term != '':
          login_attr = self.getConfProperty('LDAPUserFolder.login_attr',userFldr.getProperty('_login_attr'))
          users.extend(userFldr.findUser(search_param=login_attr,search_term=search_term))
      elif userFldr.meta_type == 'Pluggable Auth Service':
        if search_term != '':
          login_attr = 'login'
          for user in userFldr.searchUsers(login=search_term,id=None):
            plugin = getattr(userFldr,user['pluginid'])
            append = True
            if plugin.meta_type == 'ZODB User Manager':
              login_name = user[login_attr]
              append = search_term == '' or \
                (login_name.find(search_term) >= 0 and not exact_match) or \
                (login_name == search_term and exact_match)
            if append:
              users.append(user)
      else:
        login_attr = 'name'
        for userName in userFldr.getUserNames():
          if without_node_check or (local_userFldr == userFldr) or self.get_local_roles_for_userid(userName):
            if (exact_match and search_term==userName) or \
               search_term == '' or \
               search_term.find(userName) >= 0:
              users.append({'name':userName})
      for user in users:
        login_name = user[login_attr]
        d = {}
        d['localUserFldr'] = userFldr
        d['name'] = login_name
        d['user_id_'] = login_name
        d['user_id'] = login_name
        d['roles'] = []
        d['domains'] = []
        extras = ['pluginid','givenName','sn','ou']
        luf = None
        plugin = None
        _uid_attr = None
        uid = None
        if userFldr.meta_type == 'LDAPUserFolder':
          luf = userFldr
        elif userFldr.meta_type == 'Pluggable Auth Service':
          pluginid = user['pluginid']
          plugin = getattr(userFldr,pluginid)
          if plugin.meta_type == 'LDAP Multi Plugin':
            for o in plugin.objectValues('LDAPUserFolder'):
              luf = o
              break
        if luf is not None:
          _login_attr = self.getConfProperty('LDAPUserFolder.login_attr',luf.getProperty('_login_attr'))
          _uid_attr = self.getConfProperty('LDAPUserFolder.uid_attr',luf.getProperty('_uid_attr'))
          if _uid_attr != _login_attr:
            uid = user[_uid_attr]
        elif plugin is not None:
          _uid_attr = login_name
          uid = plugin.getUserIdForLogin(_uid_attr)
        if uid is not None:
          d['user_id_'] = uid
          try:
            if uid.startswith('\x01\x05\x00\x00'):
              import binascii
              uid = binascii.b2a_hex(buffer(uid))
          except:
            _globals.writeError(self,'[getValidUserids]: _uid_attr=%s'%_uid_attr)
          d['user_id'] = uid
          if len(filter(lambda x:x['id']=='user_id',c))==0:
            c.append({'id':'user_id','name':_uid_attr.capitalize(),'type':'string'})
          c = filter(lambda x:x['id']!=_uid_attr,c)
          extras = filter(lambda x:x!=_uid_attr,extras)
        for extra in user.keys():
          if extra == 'pluginid':
            pluginid = user[extra]
            plugin = getattr(userFldr,pluginid)
            d['plugin'] = plugin
            editurl = userFldr.absolute_url()+'/'+user.get('editurl','%s/manage_main'%pluginid)
            container = userFldr.aq_parent
            v = '<a href="%s" title="%s" target="_blank"><img src="%s"/></a>'%(editurl,'%s.%s (%s)'%(container.id,plugin.title_or_id(),plugin.meta_type),plugin.icon)
            t = 'html'
          else:
            v = unicode(user[extra],encoding).encode('utf-8')
            t = 'string'
          d[extra] = v
          if extra in extras and len(filter(lambda x:x['id']==extra,c))==0:
            c.append({'id':extra,'name':extra.capitalize(),'type':t})
        if exact_match and user[login_attr].lower() == search_term.lower():
          return d
        records.append(d)
      if exact_match:
        return None
      if columns is None:
        columns = c
      return {'columns':columns,'records':records}
  
  
    # --------------------------------------------------------------------------
    #  AccessManager.findUser:
    # --------------------------------------------------------------------------
    def findUser(self, name):
      user = self.getValidUserids(search_term=name,exact_match=True)
      if user is not None:
        userFldr = user['localUserFldr']
        # Change password?
        if userFldr.meta_type == 'User Folder':
          user['password'] = True
        elif userFldr.meta_type == 'Pluggable Auth Service' and user['plugin'].meta_type == 'ZODB User Manager':
          user['password'] = True
        # Details
        user['details'] = []
        if user.has_key('user_id'):
          name = 'user_id'
          label = 'User Id'
          value = user['user_id']
          user['details'].append({'name':name,'label':label,'value':value})
        # LDAP schema
        ldapUserFldr = None
        if userFldr.meta_type == 'LDAPUserFolder':
          ldapUserFldr = userFldr
        elif userFldr.meta_type == 'Pluggable Auth Service' and user['plugin'].meta_type == 'LDAP Multi Plugin':
          ldapUserFldr = getattr(user['plugin'],'acl_users')
        if ldapUserFldr is not None:
          details = ldapUserFldr.getUserDetails(encoded_dn=user['dn'],format='dictionary')
          for schema in ldapUserFldr.getLDAPSchema():
            name = schema[0]
            label = schema[1]
            value = user.get(name,'')
            user['details'].append({'name':name,'label':label,'value':value})
          # User ID
          _login_attr = self.getConfProperty('LDAPUserFolder.login_attr',ldapUserFldr.getProperty('_login_attr'))
          _uid_attr = self.getConfProperty('LDAPUserFolder.uid_attr',ldapUserFldr.getProperty('_uid_attr'))
          if _uid_attr != _login_attr:
            user['details'] = filter(lambda x:x['name'] not in [_uid_attr],user['details'])
      return user


    # --------------------------------------------------------------------------
    #  AccessManager.getUserName:
    # --------------------------------------------------------------------------
    def getUserName(self, uid):
      d = self.getSecurityUsers()
      for k in d.keys():
        if d.get('user_id_',k) == uid:
          return k
      return None

    # --------------------------------------------------------------------------
    #  AccessManager.setUserAttr:
    # --------------------------------------------------------------------------
    def setUserAttr(self, user, name, value):
      user = getUserId(user)
      root = self.breadcrumbs_obj_path()[0]
      d = root.getConfProperty('ZMS.security.users',{})
      i = d.get(user,{})
      if name == 'nodes' and type(value) is dict:
        t = {}
        for nodekey in value.keys():
          node = self.getLinkObj(nodekey)
          if node is not None:
            newkey = root.getRefObjPath(node)
            t[newkey] = value[nodekey]
        value = t
      i[name] = value
      d[user] = i.copy()
      root.setConfProperty('ZMS.security.users',d.copy())

    # --------------------------------------------------------------------------
    #  AccessManager.getUserAttr:
    # --------------------------------------------------------------------------
    def getUserAttr(self, user, name=None, default=None):
      user = getUserId(user)
      d = self.getSecurityUsers()
      if name is None:
        v = d.get(user,None)
      else:
        i = d.get(user,{})
        v = i.get(name,default)
      return v

    # --------------------------------------------------------------------------
    #  AccessManager.delUserAttr:
    # --------------------------------------------------------------------------
    def delUserAttr(self, user):
      user = getUserId(user)
      root = self.breadcrumbs_obj_path()[0]
      d = root.getConfProperty('ZMS.security.users',{})
      try:
        del d[user]
        root.setConfProperty('ZMS.security.users',d)
      except:
        _globals.writeError(root,'[delUserAttr]: user=%s not deleted!'%user)

    # --------------------------------------------------------------------------
    #  AccessManager.initRoleDefs:
    #
    #  Init Role-Definitions and Permission Settings
    # --------------------------------------------------------------------------
    def initRoleDefs(self):
    
      # Init Roles.
      for role in role_defs.keys():
        role_def = role_defs[role]
        # Add Local Role.
        if not role in self.valid_roles():
            self._addRole(role)
        # Set permissions for Local Role.
        self.manage_role(role_to_manage=role,permissions=role_permissions(self,role))
      
      # Clear acquired permissions.
      self.manage_acquiredPermissions([])
      
      # Grant public access.
      self.synchronizePublicAccess()


    # --------------------------------------------------------------------------
    #  AccessManager.getUserAdderPlugin:
    # --------------------------------------------------------------------------
    def getUserAdderPlugin(self):
      userFldr = self.getUserFolder()
      if userFldr.meta_type == 'User Folder':
        return UserFolderIAddUserPluginWrapper(userFldr)
      elif userFldr.meta_type == 'Pluggable Auth Service':
        for plugin_id in userFldr.plugins.getAllPlugins('IUserAdderPlugin')['active']:
          plugin = getattr(userFldr,plugin_id)
          return plugin
      return None


    # --------------------------------------------------------------------------
    #  AccessManager.getUserFolder:
    # --------------------------------------------------------------------------
    def getUserFolder(self):
      root = self.breadcrumbs_obj_path()[0]
      updateVersion(root)
      home = root.getHome()
      if 'acl_users' in home.objectIds():
        userFldr = home.acl_users
      else:
        # Create default user-folder.
        userFldr = UserFolder()
        home._setObject(userFldr.id, userFldr)
      return userFldr


    ############################################################################
    ###
    ###  Local Users
    ###
    ############################################################################

    # ------------------------------------------------------------------------------
    #  AccessManager.purgeLocalUsers
    # ------------------------------------------------------------------------------
    def purgeLocalUsers(self, ob=None, valid_userids=[], invalid_userids=[]):
      rtn = ""
      if ob is None:
        ob = self
        d = self.getSecurityUsers()
        for userid in d.keys():
          nodes = self.getUserAttr(userid,'nodes',{}) 
          for node in nodes.keys():
              target = self.getLinkObj(node)
              if target is None:
                self.delLocalUser(userid, node)
                rtn += userid + ": remove " + node + "<br/>"
      
      for local_role in ob.get_local_roles():
        b = False
        userid = local_role[0]
        userroles = local_role[1]
        if 'Owner' not in userroles:
          if userid not in valid_userids and userid not in invalid_userids:
            name = self.getUserName(userid)
            user = ob.findUser(name)
            if user is None:
              invalid_userids.append(userid)
            else:
              valid_userids.append(userid)
          if userid in valid_userids:
            nodes = self.getUserAttr(userid,'nodes',{})
            if len(filter(lambda x: (x=="{$}" and ob.id=="content") or x=="{$%s}"%ob.id or x.endswith("/%s}"%ob.id),nodes.keys()))==0:
              b = True
          elif userid in invalid_userids:
            b = True
        if b:
          rtn += ob.absolute_url()+ " " + userid + ": remove " + str(userroles) + "<br/>"
          delLocalRoles(ob,userid)
      
      # Process subtree.
      for subob in ob.objectValues(ob.dGlobalAttrs.keys()):
        rtn += self.purgeLocalUsers(subob, valid_userids, invalid_userids)
      
      return rtn


    # --------------------------------------------------------------------------
    #  AccessManager.toggleUserActive:
    # --------------------------------------------------------------------------
    def toggleUserActive(self, id):
      active = self.getUserAttr(id,'attrActive',1)
      attrActiveStart = self.parseLangFmtDate(self.getUserAttr(id,'attrActiveStart',None))
      if attrActiveStart is not None:
        dt = DateTime(time.mktime(attrActiveStart))
        active = active and dt.isPast()
      attrActiveEnd = self.parseLangFmtDate(self.getUserAttr(id,'attrActiveEnd',None))
      if attrActiveEnd is not None:
        dt = DateTime(time.mktime(attrActiveEnd))
        active = active and (dt.isFuture() or (dt.equalTo(dt.earliestTime()) and dt.latestTime().isFuture()))
      nodes = self.getUserAttr(id,'nodes',{})
      for node in nodes.keys():
        ob = self.getLinkObj(node)
        if ob is not None:
          user_id = self.getUserAttr(id,'user_id_',id)
          if active:
            roles = nodes[node].get('roles',[])
            setLocalRoles(ob,user_id,roles)
          else:
            delLocalRoles(ob,user_id)


    # --------------------------------------------------------------------------
    #  AccessManager.setLocalUser:
    # --------------------------------------------------------------------------
    def setLocalUser(self, id, node, roles, langs):
      
      # Set user id.
      user = self.findUser(id)
      self.setUserAttr(id, 'user_id_', user['user_id_'])
      
      # Insert node to user-properties.
      root = self.breadcrumbs_obj_path()[0]
      nodes = root.getUserAttr(id,'nodes',{})
      ob = self.getLinkObj(node)
      newkey = root.getRefObjPath(ob)
      nodes[newkey] = {'langs':langs,'roles':roles}
      root.setUserAttr(id,'nodes',nodes)
      roles = list(roles)
      if 'ZMSAdministrator' in roles:
        roles.append('Manager')
      
      # Set local roles in node.
      ob = self.getLinkObj(node)
      if ob is not None:
        user_id = self.getUserAttr(id,'user_id_',id)
        setLocalRoles(ob,user_id,roles)


    # --------------------------------------------------------------------------
    #  AccessManager.delLocalUser:
    # --------------------------------------------------------------------------
    def delLocalUser(self, id, node):
      
      # Delete node from user-properties.
      root = self.breadcrumbs_obj_path()[0]
      nodes = root.getUserAttr(id,'nodes',{})
      if nodes.has_key(node): 
        del nodes[node]
        root.setUserAttr(id,'nodes',nodes)
      
      # Delete local roles in node.
      ob = root.getLinkObj(node)
      if ob is not None:
        user_id = root.getUserAttr(id,'user_id_',id)
        delLocalRoles(ob,user_id)


    ############################################################################
    ###
    ###  Properties
    ###
    ############################################################################

    # Management Interface.
    # ---------------------
    manage_users = PageTemplateFile('zpt/ZMS/manage_users', globals())
    manage_users_sitemap = PageTemplateFile('zpt/ZMS/manage_users_sitemap', globals())

    ############################################################################
    #  AccessManager.manage_roleProperties:
    #
    #  Change or delete roles.
    ############################################################################
    def manage_roleProperties(self, btn, key, lang, REQUEST, RESPONSE=None):
      """ AccessManager.manage_roleProperties """
      message = ''
      messagekey = 'manage_tabs_message'
      id = REQUEST.get('id','')
      
      try:
          # Cancel.
          # -------
          if btn in [ self.getZMILangStr('BTN_CANCEL'), self.getZMILangStr('BTN_BACK')]:
            id = ''
          
          # Insert.
          # -------
          if btn == self.getZMILangStr('BTN_INSERT'):
            if key=='obj':
              id = REQUEST.get('newId').strip()
              #-- Add local role.
              home = self.aq_parent
              if id not in home.valid_roles():
                home._addRole(role=id,REQUEST=REQUEST)
              #-- Prepare nodes from config-properties.
              security_roles = self.getConfProperty('ZMS.security.roles',{})
              security_roles[id] = {}
              security_roles = security_roles.copy()
              self.setConfProperty('ZMS.security.roles',security_roles)
              #-- Assemble message.
              message = self.getZMILangStr('MSG_INSERTED')%self.getZMILangStr('ATTR_ROLE')
            elif key=='attr':
              #-- Insert node to config-properties.
              node = REQUEST.get('node')
              roles = REQUEST.get('roles',[])
              if not type(roles) is list: roles = [roles]
              security_roles = self.getConfProperty('ZMS.security.roles',{})
              dict = security_roles.get(id,{})
              dict[node] = {'roles':roles}
              security_roles[id] = dict
              security_roles = security_roles.copy()
              self.setConfProperty('ZMS.security.roles',security_roles)
              #-- Set permissions in node.
              ob = self.getLinkObj(node)
              permissions = []
              for role in roles:
                permissions = ob.concat_list(permissions,role_permissions(self,role.replace(' ','')))
              ob.manage_role(role_to_manage=id,permissions=permissions)
              #-- Assemble message.
              message = self.getZMILangStr('MSG_INSERTED')%self.getZMILangStr('ATTR_NODE')
          
          # Delete.
          # -------
          elif btn in ['delete', self.getZMILangStr('BTN_DELETE')]:
            if key=='obj':
              #-- Delete local role.
              for home in [self,self.aq_parent]:
                if id in home.valid_roles():
                  home._delRoles(roles=[id],REQUEST=REQUEST)
              #-- Delete nodes from config-properties.
              security_roles = self.getConfProperty('ZMS.security.roles',{})
              if security_roles.has_key(id): del security_roles[id]
              security_roles = security_roles.copy()
              self.setConfProperty('ZMS.security.roles',security_roles)
              id = ''
            elif key=='attr':
              security_roles = self.getConfProperty('ZMS.security.roles',{})
              dict = security_roles.get(id,{})
              nodekeys = REQUEST.get('nodekeys',[])
              for nodekey in nodekeys:
                #-- Delete node from config-properties.
                if dict.has_key(nodekey):
                  del dict[nodekey]
                #-- Delete permissions in node.
                permissions = []
                ob = self.getLinkObj(nodekey)
                if ob is not None:
                  ob.manage_role(role_to_manage=id,permissions=permissions)
              security_roles[id] = dict
              security_roles = security_roles.copy()
              self.setConfProperty('ZMS.security.roles',security_roles)
            #-- Assemble message.
            message = self.getZMILangStr('MSG_DELETED')%int(1)
      
      except:
        message = _globals.writeError(self,"[manage_roleProperties]")
        messagekey = 'manage_tabs_error_message'
      
      # Return with message.
      if RESPONSE:
        target = REQUEST.get( 'manage_target', 'manage_users')
        target = self.url_append_params( target, { 'lang': lang, messagekey: message, 'id':id})
        return RESPONSE.redirect(target)


    ############################################################################
    #  AccessManager.manage_userProperties:
    #
    #  Change or delete users.
    ############################################################################
    def manage_userProperties(self, btn, key, lang, REQUEST, RESPONSE=None):
      """ AccessManager.manage_userProperties """
      message = ''
      messagekey = 'manage_tabs_message'
      id = REQUEST.get('id','')
      
      try:
        # Cancel.
        # -------
        if btn in [ self.getZMILangStr('BTN_CANCEL'), self.getZMILangStr('BTN_BACK')]:
          id = ''
        
        # Add.
        # ----
        if btn == self.getZMILangStr('BTN_ADD'):
          id = REQUEST.get('newId','')
          newPassword = REQUEST.get('newPassword','')
          newConfirm = REQUEST.get('newConfirm','')
          newEmail = REQUEST.get('newEmail','')
          userAdderPlugin = self.getUserAdderPlugin()
          userAdderPlugin.doAddUser( id, newPassword)
          self.setUserAttr( id, 'email', newEmail)
          #-- Assemble message.
          message = self.getZMILangStr('MSG_INSERTED')%self.getZMILangStr('ATTR_USER')
        
        # Insert.
        # -------
        elif btn == self.getZMILangStr('BTN_INSERT'):
          langs = REQUEST.get('langs',[])
          if not type(langs) is list: langs = [langs]
          roles = REQUEST.get('roles',[])
          if not type(roles) is list: roles = [roles]
          node = REQUEST.get('node')
          ob = self.getLinkObj(node)
          docElmnt = ob.getDocumentElement()
          node = docElmnt.getRefObjPath(ob)
          docElmnt.setLocalUser(id, node, roles, langs)
          #-- Assemble message.
          message = self.getZMILangStr('MSG_INSERTED')%self.getZMILangStr('ATTR_NODE')
        
        # Change.
        # -------
        elif btn == self.getZMILangStr('BTN_SAVE'):
          if key=='obj':
            attrActive = self.getUserAttr(id,'attrActive',1)
            newAttrActive = REQUEST.get('attrActive',0)
            user = self.findUser(id)
            if user.get('password')==True:
              password = REQUEST.get('password','******')
              confirm = REQUEST.get('confirm','')
              updateUserPassword(self,user,password,confirm)
            self.setUserAttr(id,'forceChangePassword',REQUEST.get('forceChangePassword',0))
            self.setUserAttr(id,'attrActive',newAttrActive)
            self.setUserAttr(id,'attrActiveStart',self.parseLangFmtDate(REQUEST.get('attrActiveStart')))
            self.setUserAttr(id,'attrActiveEnd',self.parseLangFmtDate(REQUEST.get('attrActiveEnd')))
            self.setUserAttr(id,'email',REQUEST.get('email','').strip())
            self.setUserAttr(id,'profile',REQUEST.get('profile','').strip())
            self.setUserAttr(id,'user_id',REQUEST.get('user_id','').strip())
            if attrActive != newAttrActive:
              self.toggleUserActive(id)
          elif key=='attr':
            pass
          #-- Assemble message.
          message = self.getZMILangStr('MSG_CHANGED')
        
        # Delete.
        # -------
        elif btn in ['delete', 'remove', self.getZMILangStr('BTN_DELETE')]:
          if key=='obj':
            #-- Delete user.
            deleteUser(self,id)
            #-- Remove user.
            if btn == 'remove':
              userAdderPlugin = self.getUserAdderPlugin()
              userAdderPlugin.removeUser( id)
            id = ''
            #-- Assemble message.
            message = self.getZMILangStr('MSG_DELETED')%int(1)
          elif key=='attr':
            #-- Delete local user.
            nodekeys = REQUEST.get('nodekeys',[])
            for nodekey in nodekeys:
              try:
                self.delLocalUser(id, nodekey)
              except:
                _globals.writeError(self,'can\'t delLocalUser for nodekey=%s'%nodekey)
            #-- Assemble message.
            message = self.getZMILangStr('MSG_DELETED')%int(len(nodekeys))
        
        # Invite.
        # -------
        elif btn in ['invite', self.getZMILangStr('BTN_INVITE')]:
          email = self.getUserAttr(id,'email','')
          nodekeys = REQUEST.get('nodekeys',[])
          if len(email) > 0 and len(nodekeys) > 0:
            # Send notification.
            # ------------------
            #-- Recipient
            mto = email
            #-- Body
            userObj = self.findUser(id)
            mbody = []
            mbody.append(self.getTitle(REQUEST)+' '+self.getHref2IndexHtml(REQUEST))
            mbody.append('\n')
            mbody.append('\n%s: %s'%(self.getZMILangStr('ATTR_ID'),id))
            mbody.append('\n')
            for node in nodekeys:
              ob = self.getLinkObj(node)
              if ob is not None:
                mbody.append('\n * '+ob.getTitlealt(REQUEST)+' ['+ob.display_type(REQUEST)+']: '+ob.absolute_url()+'/manage')
            mbody.append('\n')
            mbody.append('\n' + self.getZMILangStr('WITH_BEST_REGARDS'))
            mbody.append('\n' + str(REQUEST['AUTHENTICATED_USER']))
            mbody.append('\n-------------------------------')
            mbody = ''.join(mbody)
            #-- Subject
            msubject = '%s (invitation)'%self.getTitlealt(REQUEST)
            #-- Send
            self.sendMail(mto,msubject,mbody,REQUEST)
            #-- Assemble message.
            message = self.getZMILangStr('MSG_CHANGED')
        
      except:
        message = _globals.writeError(self,"[manage_userProperties]")
        messagekey = 'manage_tabs_error_message'
      
      # Return with message.
      if RESPONSE:
        target = REQUEST.get( 'manage_target', 'manage_users')
        target = self.url_append_params( target, { 'lang': lang, messagekey: message, 'id':id})
        return RESPONSE.redirect(target)

################################################################################
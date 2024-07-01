## Script (Python) "ZMSNote.standard_json_docx"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=zmscontext=None,options=None
##title=py: JSON-DOCX Template
##
# --// standard_json_docx //--
from Products.zms import standard
request = zmscontext.REQUEST
id = zmscontext.id
text = zmscontext.attr('text')
author = zmscontext.attr('change_uid')
# date = '2024-01-01T00:00:00Z'
date = '%sZ'%standard.format_datetime_iso(zmscontext.attr('change_dt'))[0:-6]

blocks = []

docxml = f'''
  <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:commentRangeStart id="{id}" />
    <w:r>
      <w:commentReference id="{id}" />
    </w:r>
    <w:commentRangeEnd id="{id}" />
    <w:comment id="{id}" author="{author}" date="{date}">
      <w:p>
        <w:r>
          <w:t>{text}</w:t>
        </w:r>
      </w:p>
    </w:comment>
  </w:p>
'''

text = 'ZMSNote: %s, %s\n%s)'%(author, date, text)

blocks.append(
	{
		'id': id,
		'meta_id': zmscontext.meta_id,
		'parent_id': zmscontext.getParentNode().id,
		'parent_meta_id': zmscontext.getParentNode().meta_id,
		'docx_format': 'MacroText',
		'content': text
	}
)

return blocks
# --// /standard_json_docx //--

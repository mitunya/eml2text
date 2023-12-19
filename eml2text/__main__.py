import sys
import os
import io
import re
import email
import locale
import argparse

##
def mime_decode(_str):
    ret = []
    if _str is None:
        return ''
    for fragment, encoding in email.header.decode_header(_str):
        if encoding is None:
            if type(fragment) is str:
                ret.append(fragment)
            elif type(fragment) is bytes:
                ret.append(str(fragment.decode()))
        elif encoding == 'unknown':
            # fragment : =?UNKNOWN?Q?=....
            ret.append(str(fragment))
        else:
            # encoding : iso-2022-jp, utf-8, ....
            ret.append( str(fragment.decode(encoding, 'ignore')) )
    return ''.join(ret)

##
def listed_continuation_line(iobuf):
    def is_continuation(code):
        if type(code) is str:
            return code in [ ' ', '\t' ]
        elif type(code) is bytes:
            return code in [ b' ', b'\t' ]
        elif type(code) is int:
            return code in [ 32, 9 ]

    headers = []
    #with io.BytesIO(iobuf) as f:
    with io.BytesIO(iobuf) as f0, io.TextIOWrapper(f0, encoding='utf-8') as f:
        t = []
        line = f.readline()
        #print(line)
        while line:
            line = line.decode() if isinstance(line, bytes) else line
            if line == '\r\n' or line == '\n' :
                break
            elif not is_continuation(line[0]):
                if t:
                    headers.append(t)
                t = [ line ]
            else:
                t.append(line)
            line = f.readline()
    return headers

def print_header(headers, msg, ofp=sys.stdout):
    headerKeys = []
    for line in headers:
        h = line[0].split(':')
        headerKeys.append(h[0])
        if h[0].lower() in [ 'from', 'to', 'cc', 'bcc', 'subject', ] :
            print("{:s}: {:s}".format(h[0], mime_decode(msg.get(h[0]))), file=ofp)
        else:
            for l in line:
                print(l, end='', file=ofp)

def mailPayload(msg) : # -> [ (content_type, name, data), ... ]
    def is_attachment(obj):
        '''see if obj is an attachment'''
        s=obj['Content-Disposition']
        return s and s.startswith('attachment')

    def part_content(contents) -> str:
        payload = contents.get_payload(decode=True)
        charset = contents.get_content_charset()
        if charset:
            payload = payload.decode(charset, "ignore")
        else:
            payload = payload.decode()
        return payload

    payload = []
    if msg.is_multipart() :
        for part in msg.walk():
            if not part.is_multipart():
                if is_attachment(part) :
                    name = mime_decode(part.get_filename())
                    charset = part.get_content_charset()
                    if part.get_content_charset():
                        payload.append( (part.get_content_type(), name, part_content(part)) )
                    else:
                        payload.append( (part.get_content_type(), name, data) )
                else:
                    payload.append( (part.get_content_type(), None, part_content(part)) )
    else:
        payload.append( (msg.get_content_type(), None, part_content(msg)) )
    return payload

def print_mail(buf, ofp=sys.stdout):
    msg = email.message_from_bytes(buf)
    if msg:
        print_header(listed_continuation_line(buf), msg, ofp)
        print('', file=ofp)
        sep = ''
        for b in mailPayload(msg):
            if msg.is_multipart():
                r = re.match('.*\sboundary\s*=\s*(.*)', msg.get('content-type'), re.MULTILINE | re.DOTALL)
                sep = r.group(1)[1:-1] if r.group(1)[0] in ['\'', '\"',] else r.group(1)
                nam = '  filename='+b[1] if b[1] else ''
                print(sep, nam, file=ofp)
            print(b[2], file=ofp)
        if sep : print(sep + '--', file=ofp)

def getargs():
    parser = argparse.ArgumentParser()
    #parser.add_argument("-V", "--version", action='store_true', dest='showVersion',
    #                    help="show version")
    #parser.add_argument("-v", "--verbose", action='store_true',
    #                    help="increase output verbosity")
    parser.add_argument("-o", "--output", dest='output', default='-',
                        help="output filename, default stdout.")
    parser.add_argument(dest='files', action='store', nargs='*')
    args = parser.parse_args()
    return args

def main():
    def make_outstream():
        oencode = locale.getpreferredencoding()
        if args.output in [ 'stdout', '-' ] :
            return os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding=oencode, errors='replace')
        else:
            return open(args.output, 'w', encoding=oencode, errors='replace')

    args = getargs()
    if len(args.files) == 0:
        with os.fdopen(os.dup(sys.stdin.fileno()), 'rb') as ifp, make_outstream() as ofp:
            buf = ifp.read()
            print_mail(buf, ofp)
    else:
        for file in args.files:
            try:
                with open(file, 'rb') as ifp, make_outstream() as ofp:
                    buf = ifp.read()
                    print_mail(buf, ofp)
            except PermissionError:
                print("permission error for write file {}, or read file {}".format(args.output, file), file=sys.stderr)
                return 1
            except FileNotFoundError:
                print("{} not found".format(file), file=sys.stderr)
                return 1
            except Exception as ex:
                emsg = "An exception of type {0} occurred. Arguments:\n{1!r}".format(type(ex).__name__, ex.args)
                print(emsg, file=sys.stderr)
                return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

## ends

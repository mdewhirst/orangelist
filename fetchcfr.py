# -*- coding: utf-8 -*-
# Copyright © 2016 Climate Pty Ltd
# This script is part of SharedSDS free open source GHS classification software
# SharedSDS is free software subject to the terms of the GNU GPL v3
# Generously repaired by Clinton Hall on 9 June 2016

import os
import requests  # you need to "pip install requests"


#  URL for the USA DG list website
cfr_url = 'http://www.ecfr.gov/cgi-bin/text-idx?SID=9bf53f6236da46a52884a2432a775a3e&mc=true&node=pt49.2.172&rgn=div5#se49.2.172_1101'
cfrpath = "/var/www/data/ssds/us/"
if not os.path.isdir(cfrpath):
    os.makedirs(cfrpath)


def fetchcfr(cfrurl=cfr_url, outfile=os.path.join(cfrpath, "cfr.html")):
    """ This script fetches the page and scans it for the DG list and
    writes that out in three local files being cfr.html, cfr.csv and
    cfr.txt which is in a format easy to import into a database. This
    all updates itself from the source whenever it is run.

    The USA table has roman font for PSN and italics for descriptions
    where the Orange book uses upper and lower case respectively. So we
    massage it accordingly.

    """

    print("\nPlease wait while the USA psn list is retrieved")
    # requests is a very nice package
    response = requests.get(cfrurl)

    with open(outfile, "w") as page:
        tables = 0
        start = False
        current = ""
        lines = list()
        # response.text contains the page source html
        # split() produces a python list
        biglines = response.text.split("</tr>")
        for line in biglines:
            line = line.strip()
            if line:
                if not start:
                    if '<p class="updated">' in line:
                        current = line.split('<p class="updated">')[1].split("</p>")[0]

                    if '<tr><td align="center" class="gpotbl_cell" scope="row">&nbsp;&nbsp;</td>' in line:
                        start = True
                        print("Got the 172.101 list - %s" % current)
                        print("Tweaking spelling")
                    elif '<p class="gpotbl_title">List of Marine Pollutants</p>' in line:
                        start = True
                    else:
                        # don't start until the beginning of the DG table
                        continue
                if start:
                    if '</table></div></div>' in line:
                        tables += 1
                        start = False
                        # stop the loop at the end of the second table
                        if tables == 2:
                            break
                        else:
                            # separate the tables
                            lines.append("<tr><td>&nbsp;</td><td>Marine pollutants (First column PP = Severe marine pollutant)</td></tr>")
                            print("Got down to the MARPOL section")
                            print("Tweaking MARPOL spelling as well")
                    if 'class="gpotbl_cell" scope="row"' in line:
                        # the entire table is in a single *very* long
                        # line so we split it into separate rows
                        line = line.replace("ALUMINUM", "ALUMINIUM")
                        line = line.replace("luminum", "luminium")
                        line = line.replace("SULF", "SULPH")
                        line = line.replace("sulf", "sulph")
                        line = line.replace("poisonous", "toxic")
                        line = line.replace("poison", "toxic")
                        rows = line.split("</tr>")
                        for row in rows:
                            # iterate through the rows list and get rid
                            # of extraneous stuff
                            row = row.replace(' class="gpotbl_cell"', '')
                            row = row.replace(' align="left"', '')
                            row = row.replace(' align="center"', '')
                            row = row.replace(' align="right"', '')
                            row = row.replace(' scope="row"', '')
                            row = row.replace(';font-weight:inherit', '')
                            row = row.replace('&nbsp;', '')
                            # swap the tag from italic to <desc>
                            row = row.replace('<span style="font-style:italic">', "<desc>")
                            # and the closing tag
                            row = row.replace("</span>", "</desc>")
                            # swap roman to upper-case and italic to lower
                            row = changecase(row)
                            # replace the closing </tr> tag and add \n
                            # then put it in an output list
                            lines.append("%s</tr>\n" % row)
                    else:
                        # this isn't used unless we want stuff above or
                        # below the DG table.
                        line = "%s</tr>\n" % line

        # The lines list is only DG content without column headers. But
        # inspection of output reveals multiple entries for the same
        # substance where the difference is the Packing Group and the
        # first four cells are blank. We need to fill those fields in.
        # Now massage/repair the lines list into a new rows list
        savesymbol = savepsn = savehclass = saveunno = ""
        rows = list()
        for line in lines:
            # collect the values of the first four columns
            symbol, psn, hclass, unno = getfourfields(line)
            # if psn is not blank save the four values
            if psn:
                savesymbol = symbol
                savepsn = psn
                savehclass = hclass
                saveunno = unno
            else:
                # if psn is blank put the most recently saved values
                line = putfourfields(savesymbol, savepsn, savehclass, saveunno, line)
            rows.append(line)

        # finished with lines for html purposes - now to make an importable file.
        # Put it in /var/www/data/ssds/us/cfr.txt
        print("Writing %s" % os.path.join(cfrpath, "cfr.txt"))
        with open(os.path.join(cfrpath, "cfr.txt"), 'w') as txtfile:
            i = 0
            for line in rows:
                i += 1
                line = line.replace("<tr>", "")
                line = line.replace("</td>", "~")
                line = line.replace("<td/>", "~")
                line = line.replace("<td>", "")
                line = line.replace("</tr>", "")

                bits = line.split("~")
                if len(bits) > 3 :
                    if bits[3]:  # skip line if no unno
                        txtfile.write(line)

        # finished with lines for cfr.txt purposes - now to make a csv file
        # Put it in /var/www/data/ssds/us/cfr.csv
        # but first give it a simple header

        csvheader = '"(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8A", "(8B)", "(8C)", "(9A)", "(9B)", "(10A)", "(10B)", "",\n'
        print("Writing %s" % os.path.join(cfrpath, "cfr.csv"))
        with open(os.path.join(cfrpath, "cfr.csv"), 'w') as csvfile:
            csvfile.write(csvheader)
            for line in rows:
                line = line.replace("<tr>", '')
                line = line.replace("<td>", '"')
                line = line.replace("</td>", '", ')
                line = line.replace("<td/>", '"", ')
                line = line.replace("</tr>", '')
                csvfile.write(line)

        # To make a browser viewable page with column headers reverse the
        # list and add the headers and the html prefix then reverse again
        # and finish off with the html suffix
        rows.reverse()
        # These table header rows are copied directly from the website page source
        # so we put column headers on the top of the list ready to write out
        header1 = '<tr><th rowspan="3">Symbols</th><th rowspan="3">Hazardous materials descriptions and proper shipping names</th><th rowspan="3">Hazard class or Division</th><th rowspan="3">Identification Numbers</th><th rowspan="3">PG</th><th rowspan="3">Label Codes</th><th rowspan="3">Special provisions<br/>(&sect;172.102)</th><th colspan="3">(8)</th><th colspan="2">(9)</th><th colspan="2">(10)<br/>Vessel<br/>stowage</th></tr>\n'
        header2 = '<tr><th colspan="3">Packaging<br/>(&sect;173.***)</th><th colspan="2">Quantity limitations<br/>(see &sect;&sect;173.27 and 175.75)</th><th rowspan="2">Location</th><th rowspan="2">Other</th></tr>\n'
        header3 = '<tr><th>Exceptions</th><th>Non-bulk</th><th>Bulk</th><th>Passenger aircraft/rail</th><th>Cargo aircraft only</th></tr>\n'
        header4 = '<tr><td>(1)</td><td>(2)</td><td>(3)</td><td>(4)</td><td>(5)</td><td>(6)</td><td>(7)</td><td>(8A)</td><td>(8B)</td><td>(8C)</td><td>(9A)</td><td>(9B)</td><td>(10A)</td><td>(10B)</td></tr>\n'
        rows.append(header4)
        rows.append(header3)
        rows.append(header2)
        rows.append(header1)
        rows.append('<html><head></head><body><table border="1px" width="96%">\n')
        rows.reverse()
        rows.append("</table></body></html>\n")
        print("Writing %s" % outfile)
        page.writelines(rows)
        print("Done")
    return True


def changecase(row):
    """
    row is an entire <tr> row which starts with <tr> but excludes the
    closing </tr> tag because we split on that in fetchcfr(). So now we
    split the row on the opening <td> cell tag due to a variety of
    closing cell tags such as </td> and <td/>. Doing this puts the <desc>
    tag in the third cell or counting from zero, element #2

    We now want that third cell to be properly cased. That means anything
    between <desc> tags stays untouched and anything in that cell not
    between <desc> tags is uppercased. The row is returned to the caller
    exactly as received except for those changes.
    """
    # split the <tr> row into <td> cells
    cells = row.split("<td>")  # desc can only be in cells[2]
    if "<desc>" in cells[2]:
        cells[2] = dedesc(cells[2])
    else:
        cells[2] = uppercase(cells[2])

    # rows beginning G (mostly N.O.S.) require a technical chemical name
    # so we add (...) which will probably be manually replaced later
    if "G" in cells[1]:
        cells[2] = cells[2].replace("</TD>", " (...)</td>")

    # put parens around the subrisk labels in cells[6]
    if len(cells) > 6:
        cell6 = cells[6].replace("</td>", "")
        if cell6:
            cells[6] = "{0}</td>".format(labelparens(cell6))

    # reassemble the row and clean up before returning it
    row = "<td>".join(cells).replace("</TD>", "</td>").replace("<TD/>", "<td/>")
    return row


def dedesc(cell2):
    """ cell can start with <desc> or not. So there are two cases.
    However, cells may have zero or more <desc> tags. We will avoid
    calling this method if it is zero so that makes it 'one or more'

    Startswith <desc>? --> get description out and append to list
        delete the description now it is saved in the list
    No? --> split on <desc>, uppercase element[0] and append to list
        delete the psn now it is saved in the list
    Then we are back to the first case . Feels like an iterator.

    All spaces and punctuation are retained.
    """
    assert "<desc>" in cell2
    cell = cell2    # work with (ie decrement) a *copy* of cell2
    bits = list()   # this will become cell2 - proper shipping name
    while True:
        if cell:
            if cell.startswith("<desc>"):
                # split on the first closing tag
                pieces = cell.split("</desc>", 1)
                # now drop the opening <desc> tag
                pieces[0] = pieces[0].replace("<desc>", "")
                # add the lower case description
                bits.append(pieces[0])
            else:
                # <desc> must be deeper in the text
                # so the the earlier text is PSN
                # PSN is in element[0] of the pieces list
                pieces = cell.split("<desc>", 1)
                # now put back the desc tag so the next time
                # around the loop the cell starts with <desc>
                # provided there is something in pieces[1]
                if len(pieces) == 2:
                    pieces[1] = "<desc>%s" % pieces[1]
                # add the uppercased PSN
                bits.append(uppercase(pieces[0]))
            # remove the first element
            del(pieces[0])
            # and reassemble the remaining pieces if any
            # if no pieces cell will be empty and thus "False"
            cell = "".join(pieces)
            # and loop back to see if there is more to do
        else:
            # no more text to process
            break
    if bits:
        # reassemble the passed in text and return it.
        cell2 = "".join(bits)
    return cell2


def getfourfields(line):
    symbol = psn = hclass = unno = ""
    cells = line.split("<td>")
    iii = -1
    for cell in cells:
        iii += 1
        if cell.endswith("</td>"):
            if iii == 1:
                symbol = cell.replace("</td>", "")
            if iii == 2:
                psn = cell.replace("</td>", "")
            if iii == 3:
                hclass = cell.replace("</td>", "")
            if iii == 4:
                unno = cell.replace("</td>", "")
    return symbol, psn, hclass, unno


def labelparens(cell6):
    assert cell6
    bits = cell6.split(",")
    subrisk = ""
    if len(bits) >= 2:
        for sub in bits[1:len(bits)]:
            subrisk = "{0} ({1})".format(subrisk, sub.strip())
        cell6 = "{0} {1}".format(bits[0], subrisk.strip())
    return cell6


def putfourfields(symbol, psn, hclass, unno, line):
    cells = line.split("<td>")
    # cells[0] is just <tr>
    # we also need to restore the trailing </td>
    if len(cells) > 4:
        cells[1] = "%s</td>" % symbol
        cells[2] = "%s</td>" % psn
        cells[3] = "%s</td>" % hclass
        cells[4] = "%s</td>" % unno
    return "<td>".join(cells)


def uppercase(psn):
    """ upper case with twist. If there is a prefix of n- or p- it
    must be lower case
    """
    psn = psn.upper()
    # but if prefixed with n- or p-, restore that as lower case
    psns = psn.split("-", 1)            # just do one hyphen for now
    if len(psns) == 2:                  # there is a hyphen
        if len(psns[0]) <= 2:           # a space and n or p
            psns[0] = psns[0].lower()
            psn = "-".join(psns)        # reassemble
    return psn


if __name__ == "__main__":
    fetchcfr()

#!/usr/bin/env python3

# minimize dependencies (standard library only)

from argparse import ArgumentParser
from cmd import Cmd
from sys import exit
from collections import namedtuple
from collections.abc import Iterable
from sqlite3 import connect
from datetime import date

ColumnFormat = namedtuple('ColumnFormat', ['name', 'width']) 

def formatTable(rows, columnFormats=None, **kwargs):
    
    colsep = kwargs.get('colsep', '   ')
    defaultColWidth = kwargs.get('defaultColWidth', 20)
    
    columnCount = -1
    if columnFormats is not None:
        columnCount = len(columnFormats)
        if columnCount == 0:
            columnCount = -1
    
    for i, row in enumerate(rows):
        # check number of columns
        if columnCount >= 1 and len(row) != columnCount:
            raise Exception('Row %d contains %d columns.  Expected %d columns' 
                % (i, len(row), columnCount))
            
        if i==0 and columnCount >=1:
            headings = []
            underlines = []
            for format in columnFormats:
                headings.append(format.name.ljust(format.width))
                underlines.append('-'*format.width)
            yield colsep.join(headings)
            yield colsep.join(underlines)
            
        pieces = []
        for j, column in enumerate(row):
            if columnCount < 1:
                pieces.append(str(column).ljust(defaultColWidth))
                continue
            format = columnFormats[j]
            pieces.append(str(column).ljust(format.width))    
        yield colsep.join(pieces)

class Member:
    def __init__(self, first, last):
        self.first = first
        self.last = last
        self.rowid = None
        self.introducedDate = None

    def toDict(self):
        return {
            'rowid': self.rowid,
            'first': self.first,
            'last': self.last,
            'introducedDate': self.introducedDate }

    def __str__(self):
        return str(self.toDict())


class Roster(Iterable):
    def __init__(self, dbFilePath):
        self.dbFilePath = dbFilePath
        self.conn = None
        
    def __enter__(self):
        self.conn = connect(self.dbFilePath)
        self.cursor = self.conn.cursor()
        self.createTables()
        
        return self
        
    def createTables(self):
        sql = """SELECT 
            tbl_name 
        FROM sqlite_master 
        WHERE type = 'table'
            AND tbl_name = 'members'"""
        rows = list(self.cursor.execute(sql))
        if len(rows) > 0:
            return
        
        sql = """CREATE TABLE members(
            first text,
            last text,
            introducedDate text)"""
        self.cursor.execute(sql)
    
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        return False
        
    def buildMember(self, row):
        member = Member(row[1], row[2])
        member.rowid = row[0]
        member.introducedDate = row[3]
        return member
        
    def list(self):
        """list members on the roster"""
        sql = """SELECT
            rowid,
            first,
            last,
            introducedDate
        FROM members
        ORDER BY rowid"""
        rows = list(self.cursor.execute(sql))
        return [self.buildMember(row) for row in rows]
        
    def add(self, member):
        sql = """INSERT INTO members(
                first,
                last,
                introducedDate)
            VALUES(?, ?, ?)"""
        self.cursor.execute(                                              
            sql,
            (member.first,
                member.last,
                member.introducedDate))
        self.conn.commit()
        
    def get(self, rowid):
        sql = """SELECT rowid, first, last, introducedDate
            FROM members
            WHERE rowid = ?"""
        self.cursor.execute(sql, (rowid,))
        rows = list(self.cursor)
        if len(rows) == 0:
            return None
        return self.buildMember(rows[0])
        
    def update(self, member):
        sql = """UPDATE members
            SET first = ?,
                last = ?,
                introducedDate = ?
            WHERE rowid = ?"""
        self.cursor.execute(
            sql,
            (member.first, 
                member.last, 
                member.introducedDate, 
                member.rowid))
            
    
    def __iter__(self):
        return self.list().__iter__()


            
        


class CohpyIntroShell(Cmd):
    intro = 'Welcome to the Cohpy Intro shell.'
    prompt='(cohpy intro): '
    
    def __init__(self, roster):
        super().__init__()
        self.roster = roster
    
    def do_quit(self, arg):
        """quit Cohpy Intro shell"""
        exit()

    def memberToList(self, member):
        return [
            member.rowid,
            ' '.join([member.first, member.last]),
            member.introducedDate]
        
        

    def do_list(self, arg):
        """List members on the roster"""
        print('The roster includes the following members:\n')
        lines = formatTable(
            map(self.memberToList, self.roster),
            [
                ColumnFormat('id', 4),
                ColumnFormat('name', 30),
                ColumnFormat('introduced', 12)
            ])          
        for line in lines:       
            print(line)

            
    def do_add(self, arg):
        """Add member to roster"""
        first = input('First name: ')
        last = input('Last name: ')
        member = Member(first, last)
        introducedDate = input(
            'introduced (optional. Use yyyy-mm-dd format): ')
        member.introducedDate = introducedDate
        self.roster.add(member)
        
    def validateRowid(self, rowid):
        """validates rowid (passed as string).  If it's a postive integer 
        return the value"""
        try:
            rowid = int(rowid)
        except ValueError:
            print("Invalid member id %s" % rowid)
            return None
        if rowid < 1:
            print("Member id needs to be a positive integer")
            return None
        return rowid

    def getNewValue(self, prompt, oldValue):
        value = input('%s (%s): ' % (prompt, oldValue))
        if len(value) == 0:
            return oldValue
        if len(value.strip()) == 0:
            return None
        return value

    def do_edit(self, args):
        """Edit member.  Usage Edit MEMBER_ID"""
        member = None
        rowid = args.split(' ')[0]
        
        # loop till we get a rowid which matches a member in the database
        while True:
            rowid = self.validateRowid(rowid)
            if rowid is None:
                rowid = input('Enter member id: ')
                continue
            
            member = self.roster.get(rowid)
            if member is None:
                print("No member with id of %d" % rowid)
                # rowid will get validated again, but it's the same value
                # which already passed validation
                continue
                
            break
            
        print('Editing %s %s' % (member.first, member.last))
        print('Type new value, hit enter to keep current value, or enter spaces to clear a value')
        member.first = self.getNewValue('First name', member.first)
        member.last = self.getNewValue('Last name', member.last)
        member.introducedDate = self.getNewValue('introduced date', member.introducedDate) 
        
        self.roster.update(member)
                
                
            

           
        
        

if __name__ == '__main__':
    parser = ArgumentParser(
        description="""Maintain a roster of COHPy attendees and randomly 
        select one who hasn\'t introduced him or herself recently""")
    parser.add_argument('DB_FILE', help="""Path to an sqlite file.  If the
        file doesn't exist this program will attempt to create it.""")

    dbFilePath = parser.parse_args().DB_FILE
    with Roster(dbFilePath) as roster:
        shell = CohpyIntroShell(roster)
        shell.cmdloop()




from mongoalchemy.connection import connect
import spec
import exceptions
import pymongo
import fields

class Manager(object):
    def __init__(self):
        self._collection = None

    def __get__(self, instance, owner):
        if instance is not None:
            return self

        if self._collection is None:
            db = connect(owner._meta['db'])
            self._collection = db[owner._meta['collection']]

        return Query(owner, self._collection)

class Query(object):
    def __init__(self, document_cls, collection):
        self._document_cls = document_cls
        self._collection = collection
        self._spec = spec.QuerySpecification(None)
        self._pymongo_cursor = None
        self._fields = None

    def _transform_key_list(self, keys):
        transformed_keys = []

        for key in keys.split():
           direction = pymongo.ASCENDING

           if key[0] == '-':
               direction = pymongo.DESCENDING
           if key[0] in ('-', '+'):
               key = key[1:]

           transformed_keys.append((key, direction))

        return transformed_keys

    def ensure_index(self, key_or_list):
        indexes = self._transform_key_list(key_or_list)
        self._collection.ensure_index(indexes)
        return self

    def find(self, *expressions):
        return self.filter(*expressions).all()

    def find_one(self, *expressions):
        return self.filter(*expressions).one()

    def filter(self, *expressions):
        for expression in expressions:
            self._spec &= expression

        return self

    def filter_by(self, **kwargs):
        for k,v  in kwargs.iteritems():
            self._spec &= getattr(self._document_cls, k).eq(v)

        return self

    def exclude(self, *expressions):
        for expression in expressions:
            self._spec &= ~expression

        return self

    def exclude_by(self, **kwargs):
        for k,v  in kwargs.iteritems():
            self._spec &= ~getattr(self._document_cls, k).eq(v)

        return self

    def one(self):
        return self._document_cls.to_python(self._one())

    def _one(self):
        return self._collection.find_one(self._spec.compile(), fields=self._fields)

    def first(self, *expressions):
        try:
            return self.filter(*expressions)[0]
        except IndexError:
            raise exceptions.DoesNotExist()

    def all(self):
        return list(self)

    def with_id(self, object_id):
        return self.filter_by(_id=self._document_cls._id.to_mongo(object_id)).one()

    def in_bulk(self, object_ids):
        field = self._document_cls._id
        return  dict([(doc._id, doc) for doc in self.filter(field.in_(map(field.to_mongo, object_ids)))])

    def next(self):
        try:
            return self._document_cls.to_python(self._cursor.next())
        except StopIteration, e:
            self.rewind()
            raise e
    
    def rewind(self):
        self._cursor.rewind()
        return self

    def count(self):
        return self._cursor.count(with_limit_and_skip=True)

    def __len__(self):
        return self.count()

    def limit(self, n):
        self._cursor.limit(n)
        return self

    def skip(self, n):
        self._cursor.skip(n)
        return self

    def __getitem__(self, key):
        if isinstance(key, slice):
            self._pymongo_cursor = self._cursor[key]
            return self
        elif isinstance(key, int):
            return self._document_cls.to_python(self._cursor[key])

    def only(self, *exprs):
        self._fields = {'_cls': 1}

        for expr in exprs:
            if isinstance(expr, basestring):
                self._fields[expr] = 1
            elif isinstance(expr, fields.Field):
                self._fields[expr.name] = 1
            elif isinstance(expr, spec.Slice):
                self._fields.update(expr.compile())
                
        return self

    def sort(self, key_list):
        self._cursor.sort(self._transform_key_list(key_list))
        return self

    def explain(self, pretty=False):
        plan = self._cursor.explain()

        if pretty:
            import pprint
            plan = pprint.pformat(plan)

        return plan

    def delete(self, safe=False):
        return self._collection.remove(self._spec.compile(), safe=safe)

    def _update(self, update, safe, upsert, multi):
       try:
           self._collection.update(self._spec.compile(), update, safe=safe, upsert=upsert, multi=multi)
       except pymongo.errors.OperationFailure, err:
           raise exceptions.OperationError(unicode(err))

    def update(self, update_spec, safe=False):
        self._update(update_spec.compile(), safe, False, True)

    def update_one(self, update_spec, safe=False):
        self._update(update_spec.compile(), safe, False, False)

    def upsert(self, update_spec, safe=False):
        self._update(update_spec.compile(), safe, True, False)

    def __iter__(self):
        return self

    @property
    def _cursor(self):
        if self._pymongo_cursor is None:
            self._pymongo_cursor = self._collection.find(self._spec.compile(), fields=self._fields)

        return self._pymongo_cursor

    def __repr__(self):
        return self._spec.__repr__()
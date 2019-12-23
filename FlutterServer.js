var createError = require('http-errors');
var express = require('express');
var path = require('path');
var cookieParser = require('cookie-parser');
var logger = require('morgan');
var indexRouter = require('./routes/index');
var usersRouter = require('./routes/users');
var bodyParser = require('body-parser');
var MongoClient=require('mongodb').MongoClient;
var session = require('express-session');
var MongoStore = require('connect-mongo')(session);
var request = require("request")

var app = express();

// view engine setup
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'jade');

app.use(logger('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: 'keyboard cat',
  cookie: { maxAge:365*24*60*1000*60 },
  resave : false,
  saveUninitialized:true,
  store: new MongoStore({url:"mongodb://localhost:27017/semester",useNewUrlParser:true})
}))

const partyKeyword = {
  "KMT":["國民黨","韓國瑜","朱立倫","KMT","吳敦義"],
  "DPP":["民進","蔡英文","DPP","蘇貞昌"],
  "NPP":["時代力量","黃國昌","國昌","時力"],
  "TPP":["民眾黨","柯P","台北市長","臺北市長","台民","臺民"]
}

const newsKind = [
  "政治",
  "生活",
  "大陸",
  "財經",
  "國際",
  "地方",
  "社會",
  "體育",
  "影劇",
]

app.use("/",function(req,res,next){
  if(req.session.favorite == undefined){
    req.session.favorite = []
  }
  next()
});

app.get("/getUserId",function(req,res){
  res.send(req.session.id)
})

app.get("/searchParty",function(req,res){
  regex = partyKeyword[req.query.key].join("|")
  MongoClient.connect("mongodb://localhost:27017",{ useUnifiedTopology: true },function(err,client){
    if(err) throw err;
    client.db("semester").collection('ettoday',function(err,collection){
      collection.find({"title":{"$regex":regex}},{"_id":0}).sort("_id",-1).limit(20).toArray(function(err,items){
        responseData = {
          "data":items,
          "count":items.length
        }
        res.send(responseData);
      });
    });
  });
});

app.get("/searchingData",function(req,res){
  MongoClient.connect("mongodb://localhost:27017",{ useUnifiedTopology: true },function(err,client){
    if(err) throw err;
    client.db("semester").collection("ettoday",function(err,collection){
      collection.find({"title":{"$regex":req.query.key}},{"_id":0}).sort("_id",-1).toArray(function(err,items){
        responseData = {
          "data":items,
          "count":items.length
        }
        res.send(responseData);
      });
    });
  });
});

app.get("/newsKind",function(req,res){
  MongoClient.connect("mongodb://localhost:27017",{useUnifiedTopology:true},function(err,client){
    if(err) throw err;
    client.db("semester").collection("ettoday",function(err,collection){
      if(req.query.key == "全部"){
        collection.find({},{"_id":0}).sort("_id",-1).limit(20).toArray(function(err,items){
          responseData = {
            "data":items,
            "count":items.length
          }
          res.send(responseData);
        });
      }else if(newsKind.includes(req.query.key)){
        collection.find({"tag":req.query.key},{"_id":0}).sort("_id",-1).limit(30).toArray(function(err,items){
          responseData = {
            "data":items,
            "count":items.length
          }
          res.send(responseData);
        });
      }else{
        collection.find({"tag":{"$nin": newsKind}},{"_id":0}).sort("_id",-1).limit(30).toArray(function(err,items){
          responseData = {
            "data":items,
            "count":items.length
          }
          res.send(responseData);
        });
      }
    });
  });
});

app.get("/toggleFavorite",function(req,res){
  var imgUrl = req.query.url;
  //req.session.favorite.forEach(val=>console.log(val.title))
  //console.log("INput  "+imgUrl)
  if(req.session.favorite.some((val)=>val.img_path == imgUrl)){
    req.session.favorite = req.session.favorite.filter(val=>val.img_path != imgUrl);
    res.send("delete completed");
  }else{
    MongoClient.connect("mongodb://localhost:27017",{ useUnifiedTopology: true },function(err,client){
      if(err) throw err;
      client.db("semester").collection("ettoday",function(err,collection){
        collection.find({"img_path":imgUrl},{"_id":0}).toArray(function(err,items){
          req.session.favorite.push(items[0])
          //req.session.favorite.forEach(val=>console.log(val.img_path))
          res.send("add completed");
        });
      });
    });
  }
});

app.get("/getFavorite",function(req,res){
  res.send(req.session.favorite);
});

app.get("/getSearching",function(req,res){
  var text = req.query.text
  console.log(text)
  request.post("http://localhost:3500/sentSims",{json:true,body:text},function(error,response,body){
    res.send(body)
  })
})

app.get("/getRecomm",function(req,res){
  if(req.session.favorite.length == 0){res.send([])}
  else{
  favorite = req.session.favorite.map((items)=>items["title"])
  request.post("http://localhost:3500/Recomm",{json:true,body:favorite},function(err,response,body){
    res.send(body)
    // MongoClient.connect("mongodb://localhost:27017",{ useUnifiedTopology: true },function(err,client){
    //   if(err) throw err;
    //   client.db("semester").collection("ettoday",function(err,collection){
    //     collection.find({"img_path":{"$in":body}},{"_id":0}).toArray(function(err,items){
    //       var orderResult = body.map((val)=>{
    //         return items.find((item)=>item["img_path"]==val)
    //       })
    //       res.send(orderResult);
    //     });
    //   });
    // });
   })
  }
})

app.get("/FakeNewsJ",function(req,res){
  console.log(req.query.text)
  request.post("http://localhost:3500/FakeNewsJ",{json:true,body:req.query.text},function(error,response,body){
    res.send(body)
  })
})

app.post("/pushFeedback",function(req,res){
  console.log(req.body.data[0])
  MongoClient.connect("mongodb://localhost:27017",{useUnifiedTopology: true },function(err,client){
    if(err) throw err;
    client.db("semester").collection("feedback",function(err,collection){
      collection.insertMany(req.body.data,function(err,rs){
        console.log(err)
        res.send("OK!")
      });
    });
  });
});



// catch 404 and forward to error handler
app.use(function(req, res, next) {
  next(createError(404));
});

// error handler
app.use(function(err, req, res, next) {
  // set locals, only providing error in development
  res.locals.message = err.message;
  res.locals.error = req.app.get('env') === 'development' ? err : {};

  // render the error page
  res.status(err.status || 500);
  res.render('error');
});

module.exports = app;
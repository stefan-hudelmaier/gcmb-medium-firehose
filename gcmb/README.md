# Medium.com Post Firehose

This is a real-time stream of medium.com blog posts. Information about new blog posts
are published via MQTT in the form of [Atom](https://en.wikipedia.org/wiki/Atom_(web_standard)) entries.

The most popular 100 tags are monitored, see below for a full list.

Here is a web app that subscribes to the stream and displays new posts: [Medium Firehose UI](https://stefan-hudelmaier.github.io/medium-firehose-ui/)

Here is an example MQTT message:

```xml
<?xml version="1.0" ?>
<entry xmlns="http://www.w3.org/2005/Atom">
  <id>https://medium.com/p/66fc2e59f977</id>
  <published>2025-05-04T07:09:12.000Z</published>
  <updated>2025-05-04T07:09:12.287Z</updated>
  <title>Can “AI” Destroy Global Business Ecosystems? Why Isn’t Anyone Talking About It?</title>
  <author>
    <name>Manoj Bhadana</name>
  </author>
  <category term="ai"/>
  <category term="design"/>
  <category term="growth"/>
  <category term="business"/>
  <category term="economy"/>
  <link title="Can “AI” Destroy Global Business Ecosystems? Why Isn’t Anyone Talking About 
    It?" rel="alternate" href="https://bhadana-manoj.medium.com/can-ai-destroy-global-business-
    ecosystems-why-isnt-anyone-talking-about-it-66fc2e59f977?source=rss------business-5" 
    type="text/html"/>
  <summary type="html">&lt;div class=&quot;medium-feed-item&quot;&gt;&lt;p class=&quot;
    medium-feed-image&quot;&gt;&lt;a href=&quot;https://bhadana-manoj.medium.com/can-ai-
    destroy-global-business-ecosystems-why-isnt-anyone-talking-about-it-66fc2e59f977
    ?source=rss------business-5&quot;&gt;&lt;img src=&quot;https://cdn-images-1.medium.com
    /max/1200/1*S4H_5B5CqNvWtW07IfdFMA.jpeg&quot; width=&quot;1200&quot;&gt;&lt;/a&gt;&lt;
    /p&gt;&lt;p class=&quot;medium-feed-snippet&quot;&gt;AI&amp;#x2019;s rapid rise
    threatens not just jobs but entire business ecosystems. As companies like Duolingo
    and Canva embrace automation, AI giants&amp;#x2026;&lt;/p&gt;&lt;p class=&quot;
    medium-feed-link&quot;&gt;&lt;a href=&quot;https://bhadana-manoj.medium.com/can-
    ai-destroy-global-business-ecosystems-why-isnt-anyone-talking-about-it-66fc2e59f977
    ?source=rss------business-5&quot;&gt;Continue reading on Medium »&lt;/a&gt;&lt;/p&gt;
    &lt;/div&gt;
  </summary>
</entry>
```

As you can see, the text of the blog post is not contained, you have to fetch it from medium.com

## Technical integration

The adapter ([GitHub project](https://github.com/stefan-hudelmaier/gcmb-medium-firehose)) subscribes to updates via PubSubHubbub aka PuSH aka WebSub ([spec](https://www.w3.org/TR/websub/)).
Medium.com sends notifications via https://superfeedr.com/ which sends update to the adapter, which in turn publishes them via MQTT.

Consuming these updates via MQTT is much easier for the client, as WebSub requires you to have a publicly reachable HTTP endpoint. MQTT on the other hand
sends push messages via a standing TCP connection.

## List of monitored tags

* technology
* programming
* money
* self-improvement
* psychology
* data-science
* science
* writing
* business
* mental-health
* relationships
* health
* design
* artificial-intelligence
* productivity
* life
* politics
* machine-learning
* culture
* humor
* education
* cryptocurrency
* history
* social-media
* startup
* books
* lifestyle
* creativity
* software-development
* travel
* leadership
* entrepreneurship
* art
* music
* python
* photography
* software-engineering
* mindfulness
* women
* deep-learning
* marketing
* javascript
* food
* ux
* coding
* film
* web-development
* future
* blockchain
* society
* sexuality
* work
* gaming
* philosophy
* sports
* space
* poetry
* economics
* spirituality
* fiction
* feminism
* climate-change
* fitness
* language
* family
* android
* innovation
* inspiration
* media
* apple
* world
* react
* parenting
* ideas
* freelancing
* math
* true-crime
* justice
* equality
* religion
* movies
* tech
* life-lessons
* cybersecurity
* internet-of-things
* product-management
* this-happened-to-me
* bitcoin
* venture-capital
* reading
* privacy
* government
* ui
* race
* data-engineering
* cooking
* finance
* data-visualization
* investing
* ux-design

Source: [https://medium.oldcai.com/](https://medium.oldcai.com/)

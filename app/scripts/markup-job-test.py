import os
import sys
import json
from openai import OpenAI


# os.environ.get('NEBIUS_API')
job_data = {}


markup_text = """
You are a helpful assistant processing text. You are identifying entities which are people, places, things, events, artworks, etc. In the following text wrap each entity in curly brackets create or reuse a unique integer identifier for each and place it inside the curly brackets separated by a pipe character with the text, also add the type of entity it is seperated by a pipe character, for example {John Doe|####|Person} where "####" is the unique integer identifier, and "Person" is entity type, the entity must be wrapped in the curly brackets, reuse that unique integer identifier for each occurrence of the same entity in the rest of the text. Return the full text do not modify the orgnial text. Some entities may span a line break, if they do remove the hyphen if there and remove the newline character. Do not put newline characters inside the curly brackets, remove any newline character inside the curly brackets. Return the full text, do not add any additonal text to the start of the response. 
Preference using the following entity types: person, institution, interview transcript, block, music group, Linking Lost Jazz "Shrine", borough, group, agent, organization, record label, place, country, state, city, neighborhood, Semantic Lab project, document, occupation, event, venue, artwork (concept), performance, archival object, technology, activity, publication, collaboration, business, guest list, press release, memorandum, letter, address list, newspaper clipping, newsletter, booklet, family, cinematic work (concept), museum, school, musical instrument, scholarly article, scholarly publication, academic journal, article, book, kinship, kinship nature, property, demographica, historic demographica, artist book, catalogue, publisher, reason for uncertainty, draft, postcard, photograph, schedule, artist statement, collection, art exhibition, annotation, sound installation artwork (concept), qualifier property, organizational chart, floor plan, form, list, manuscript, pamphlet, programme, questionnaire, receipt, telegram, moving image, concert, price descriptor, band battle, park, warehouse, casino, genre, nonprofit organization, participatory theatre, art material, civic center, USO center, dance group, sports stadium, radio station, hotel, artist's studio, continent, inverse property, symmetric property, unrealized project, benefit, brand, color, gelatin silver print, slide, polaroid, sound, sculpture, ethnic group, drawing, workshop, celebration, film screening, panel discussion, auction, presentation, street performance, walking tour, monastery, artist collective, project, education event, exhibition event, performance event, fundraising event, screening event, social event, restaurant, work, painting, film (material), sculpture (material), photograph (material), video recordings (material), relationship generation type, local union, instructions, notes, object, choreographic work (concept), dance performance, comedy performance, canal, island, air base, diary entry, field of work (class), audio-visual recording, diary, bibliographic reference, bibliography, ship, series, press packet, edge-notched card, artwork (object), installation artwork (concept), music performance, performance artwork (concept), dramatic work (concept), musical work (concept), literary work (concept), print, poster, combine painting, correspondence, periodical, newspaper, clipping, notebook, typescript, envelope, sound recording, artwork (structural class), letter to the editor, review, role, character, steamship, dissertation, language. But if a entity does not fit you may makup a new class.                             
You also add lines to the text to seperate the document into sections. Insert the text "<BLOCKBREAK/>" to divide up the document by contextual text groupings. If the text is an article group the pharagraphs together based on context. For example several pharagraphs could cover one idea or topic, group those together with one "<BLOCKBREAK/>" after all of the relevant pharagraphs.  If the text is a interview group the text by by question and answer groupings. If the text is a diary group the text based on dates. Here is the text:
[072] Diary
 Antwerp August 6 1891

[073] Diary
 August 7 1891. Antwerp
Discussed difference between Belgians and Hollanders. Is it due to the hold of the Catholic Church in Belgium?
Read “L’Intruse” by Maeterlinck,and compared it with Mrs. Augusta Webster’s “Auspicious Day.”

 Aug. 8 Antwerp The Hague 1891
Read Vol. V of Journal de J. Goncourt at breakfast. Went to Musée and saw Titian and Rubens and Flemings. Sketched ears. After lunch went to the Cathedral to see Rubens and to S. Jacques, where there is a finer Rubens. Sacristan most grumpy - pulled curtain over pictures and found it incredible that anyone should 
[074]

want to look at a picture a whole quarter of an hour. Marched uneasily up and down asking, “Est-ce fini?” Read Baedeker in train. Hist. Holland, Rise of Flemish and Dutch art.

Sunday, Aug. 9. 91. The Hague
Went to Baron Steengracht’s collection. Saw Rembrandt’s Bathsheba xx. Very large Jan Steen (family group) large portrait of a boy by Metsu. Finest A. Brauwer, drinking scene with portraits of himself, Franz Hals, etc. Afternoon went to Museum. Saw Rembrandt’s Presentation in Temple.
xxx Vanmeer [sic] von Delft, water and houses.
Paul Potter - Bull. This is a wonderful picture, painted to be the exact texture of the skin of the different animals. [075] A paradox in paint, for, although it is exactly like, the effect is not at all as we see it. P. P. died before 30. Interesting speculation as to what he might have become, with this wonderful skill with the brush. Saw Italian pictures.
Monday August 10. 1891. s’Gravenhage
Went to Museum. Sketched Sodoma - saw other pictures, especially Van Meer van Delft.
Went to Leyden. Walked about the town. Saw, after infinite difficulty, about a dozen sketch-books of Hokusai. Bought Motley’s Dutch Republicand read introduction. Dined at the restaurant Van Pijl. 4 francs. Very good. Took notes and discussed Motley in evening.
Read La Princesse Maleine by Maeterlinck of Bruxelles.

[076]

Tuesday Aug. 11. 91. s’Gravenhage
Read Motley while dressing, Goncourt at Breakfast. Went to Museum and 
sketched Sodoma again. Went to Delft. Saw Renaissance Staathuis and Church
 with Renaissance tomb of William of Nassau. Compared it with tomb in 
Salisbury Cathedral. Saw some quaint old houses. Looked for view which Vanmeer 
painted, but didn’t find it. Liked the town of the Groote Kerk. Evening strangely 
blue and violet. Read Motley.

[077] Wednesday. Aug. 12. 91. Amsterdam.
Came from The Hague here. Read Motley. Went to Museum. Saw “Night Watch” B. B. said it was a poet’s attempt to translate a commonplace subject into verse, and that it was told better and more appropriately, on the whole, in the good prose of Van du Helst, Jardin, etc. Saw a Vermeer von Delft and other Rembrandts and Franz Hals. Very tired. Read more Motley. Walked in Kalverstraat. Discussed the ways of writing history, epic and documental.

Thursday. Aug. 13.  91. Amsterdam
Went to Rijks Museum and saw Rembrandt Old Woman -Syndics - Night Watch. Franz Hals, Portraits and Regents piece, Van du Meer. Van du Helst. Pieter de Hooghe, Van du Meer. Jan Steen.
[078] Paul Potter, etc. Scoorel. Saw a wonderful majolica plate, with a round representation of a scene somewhat similar to Botticelli’s “Calumny”. Very Timote-esque. The coat of arms was like this:[drawing]
Lunched at Krasnapolski’s - good coffee. Went to the Six gallery (Heerengracht 511) and saw two Vanmeer van Delft’s - a woman pouring out water, and a street scene. This makes 11 of his pictures which B. has seen, e. g., 1 at the Hague, 

[0079]
1 in the Rijks Museum here, 2 in the Six Collection (4), 2 at Dresden (6), 1 at Berlin (7), 1 at Frankfurt (8), 1 in Vienna (9), 1 in the Borghese (10), 1 in the Louvre (11).
A wonderful Rembrandt (portrait of Burgomaster Six) done very much in Franz Hals manner. A splendid Franz Hals portrait of a man. Some Cuyps, Terborgs, Jan Steens, etc. A large Paul Potter, man on horseback, and a small one of cows.
Read Motley and de Goncourt. Enjoyed the Palace. Dutch Renaissance, very harmonious and nice. Studied German. Wrote letters. Sent “Maleine”to Miss Bradley and Miss Cooper.

[080] Friday August 14. 1891.
Read Motley going to Haarlem. Spent 2 1/2 hours in the Museum, studying Frans Hals, etc. We were perfectly fascinated with the two pictures nos. 77 & 78, painted in 1664- in a manner suggestive of Zorn and Carrière, but even more modern than either! Compared him to Shakespeare. Also found figures and treatment which Rembrandt must have copied.
The best Terburg - a Family Group - was painted very much like a Courtois. A landscape by Van der Velde was like a Hampstead Heath scene by Constable - but better! The Cornelius van Haarlems were all [081] interesting, and the pictures by Jan de Braij, while under Frans Hals’ influence, were very good. A Regents picture by Pot was also extremely good, and some portraits by Verspronck. 
Compared evolution of Hals to Velasquez, beginning where Titian left off.
Went to Fodor Museum - an absolute fraud, 1 small Meissonier and a slight sketch 
by Watteau.
 Walked through Ghetto.
Saturday Aug. 15. 91.
A day in train from Amsterdam 9. 30 to Hanover 8. 50. Missed connections. Very hot and somewhat dusty.
Read Motley all day and studied German.
[082] Sunday August 16. 1891. Brunswick

Came from Hanover -studied German in train and began Tolstoi’s “Wandelt im Licht.”Gallery closed. Saw town and churches and very nice recent buildings in Renaissance style, i. e. - new Schloss, Theater, Police Court, etc. In the Dom the tomb of Henry the Lion and Matilda his wife (done about 1200) was very remarkable and beautiful. Her face was particularly lovely, and as well modelled as anything Greek!! Found it hard to understand.
At breakfast discussed the advantages, to a writer, of having no traditions to contend with - compared Dumas fils and Ibsen. Tolstoi and the Russian novelists with the Americans. Also the skill the rich get in objects of [083] household art, such as furniture, tapestry, carpets, etc., but the rarity of their becoming connoisseurs in the higher arts. Goncourt puts it perfectly in his entry for samedi, 20 février 1875 “Les gens riches, il leur arrive parfois d’avoir du goût dans les porcelaines, dans les tapisseries, dans les meubles, dans les tabatières, dans les objets d’art industriel … il semble vraiment qu’aux richaios, sauf de très rares exceptions, est défendu le goût de l’art supérieur, - de l’art fait par les mains, qui ne sont plus des mains d’ouvrier.”
This is especially true of Americans, who really furnish their houses perfectly. However, they as buy good French pictures, or perhaps it is that they buy French pictures, and therefore can’t help getting good ones.

[in Bernhard’s hand]
[084] Monday August 17. 9
Went to the gallery in the forenoon, and found that a hail-storm a month ago had smashed the glass-roofs of the large halls, and that the pictures in them therefore were invisible. But we told the custodian we must see them even in the dark. He took us on tiptoe to the Palma, and left us at our request. As we were going out we bumped against two officials. Mutual surprise. They tried to be indignant, then assured us we had risked our lives, because glass was still falling from the roofs. Told them they must know well that when you [0087] come on purpose to see pictures you did not mind risking your life. That disarmed them, and the younger was liebenswürdig enough to offer to take us through those same halls with a lantern.
In this way we had a glimpse of two pictures that change one’s idea of their painter. One is a portrait by Rubens painted with almost the readiness, and sweat of Frans Hals. Furthermore, it is the only portrait by Rubens I have seen in which Rubens sinks himself. The other picture is Stien’s Wedding-Contract. The bride [088] and bride groom are charming beyond words.
Other things never to be forgotten are the Vermeer and some of the Rembrandts.
The Vermeer had that wonderful purity and tenderness of colouring which makes his work seem so much like the finest porcelain. In this as in the other pictures, the same light blue, the same tints of sage and pea green, and the same effects of atmosphere.
The most fascinating Rembrandt is the landscape. One would like to know where he got such a landscape. It is a scene for some strange mysterious tale in Stevenson’s best fashion. Scarcely [089] less impressive is Christ and the Magdalen, neatly and clearly done, but treated in a wonderfully, religious way. The figure of Christ at any rate is full of that humility, and sense of wonder at his own self that Rembrandt more than once gives to the face and form of Jesus. The Magdalen is a Dutch woman of Rembrandt’s own time. Very interesting also are two portraits of Rembrandt’s earliest days, one of Hugo Grotius, a clean, fresh bit of painting, and one of Grotius’ wife. Her portrait we should scarcely have known for [090] a Rembrandt. It is so firm and free from effects of atmosphere.
Finally I shall scarcely forget a little landscape by the elder Vermeer, a thing severe, quiet, with plenty of sky and spaciousness.
In the afternoon we were in the fast express to Berlin, reading Motley and studying German as we rushed thro’ the pretty towns, or past woods of white birch.
[0087-0088: small notes written by Bernhard using a fountain pen with an Italic nib]
[recto 0087]
Some people answer as if they were shutting the door with a bang.
Mothers …
[verso 0088]
Primavera. Venus-type of Judith and Fortezza, keys left hand as in latter. Mercury and all flesh tints as in Sebastiano of Berlin.
Drapery of Venus breasts and sleeves as in Judith.
With this goes well the Madonna with six saints; in the hands are same.
Michael and John Polagologos.

Feminine saint of type of 3 dancing women. This is on way to coronation in the landscape as in Venus of ____.
[in left margin] Spirit same ____ as child in Madonna with 6 saints.
[from here on in Mary’s hand]
[090] Tuesday Aug. 18. 91. Berlin
Breakfast at Bauer’s restaurant.
Went to Gallery - - - - - - - - - - ! ! 10-3.
Walked in Thiergarten. Read Layard, etc., in the evening.

[091] Wednesday, Aug. 19. 1891
Went early to gallery and went carefully through the Venetian School from Gentile da Fabriano and Antonio Vivarini to Tiepolo. Also the Veronese school.
Thursday August 20. 1891. Berlin
Florentine School at the gallery - As we were looking at a fake “Pisanello”, an American young man asked why it was fake. We were too busy to stop, but we asked him to lunch. His turned out to be from New Brunswick, and his name was Van Dyck - a circumstance which naturally led him to take [092] an interest in pictures!! He had rather good taste, but he was oppressed with profound scepticism. He said that the pictures were all so repainted that the ascriptions were a mere matter of guess-work. In fine, he turned out to be the sort of person who knows too much to want to learn, and too little to teach, or even to sympathize. Went to the Nationalgallerie.
Herr Klinsmann dined with us and we walked in the Thiergarten. We discussed the Jews in Berlin.
Friday. Aug. 21. 1891. Berlin
Ferrarese and Milanese Schools at the Gallery. Went to museum upstairs and [093] Tschudi’s study.
Herr Klinsmann took us to the International Exhibition, where there were paintings by every school but the only good one, the French. Böcklin had an absurd “Susanna and the Elders”, as modern old ___ Jews. Berenson said he would like to see the Bible illustrated by Böcklin. The Spanish painters struck me as delightful, particularly Villegas and Beuliure y Gil.
Came from Berlin to Dresden. Motley and German.

Dresden Saturday Aug. 22. 91. Hotel Rheinischerhof
Went to gallery ------ !!
Met Walter [094] Cope, Signor Costa and the Hon. Mrs. Bontine there. Saw
Belottos with Costa.
Read Motley and de Lisle Adam in the afternoon. Called on “Michael Field” and found them gone to the hospital, Miss Cooper having the Scarlet Fever. Poor things!
Went to Das Rheingold in the evening, and enjoyed it very much.
DresdenSunday August 23 1891
Gallery in morning with Costa. Read Bonhomet Triboulet by Villiers de Lisle Adam. x Restaurant Gneist [added in blue ink]

Dresden Monday August 24. 91.
Gallery in morning. Called on Michael Fields at Stadt Krankenhaus [095] where Miss Cooper is ill with Scarlet Fever. Went to Die Walkyrie in evening.

Dresden Tuesday Aug. 25. 91. 
Gallery with Costa in morning. Called on Michael Field in afternoon.
Concert on Terrace in evening.
Motley and Villiers de Lisle Adam “Histoires insolites”.
Wednesday, Aug. 26. 91. Dresden
Gallery with Costa. Met Florence Dike’s friend, Lizzie Johnston and her family. Discussed “Botticelli” Madonna. Costa thinks it genuine, B. B. not. Went to hear Siegfried in evening.

[096] Dresden. Thursday August 27. 1891
Went to Gallery and read Correggio article and discussed it. Called on Michael Fields, who were enthusiastically reading “Parsifal.”M. felt very ill in afternoon. Both sleepy in evening.

Dresden. Friday Aug. 28. 91.
Gallery in morning. Took notes of pictures. Called on Miss Bradley (Michael Field) in the afternoon. Went to Götterdämmerung in the evening and enjoyed it even more than all the others. B. remarked that Wotan was unusually [097] sensible for a god - for he retired when he perceived that he was obsolescent. B shaved off his beard!!!!
* Dresden August 30. 1891. 
Took 9. 20 train to Pötscha and walked to the Bastei through fresh, mushroom smelling pine woods. After lunch we started to walk to Shaudan but took a cul-de-sac road which landed us in a beautiful woodland temple. Walked back to Rathen and thence to Pötscha, just catching the train. The day was warm and fresh, and the sunlight enchanting. It was a day to remember all our lives. As we got off the train B. saw preparations which made him think they were about to commit a statue in the square.
[098] Dresden. Aug. 31. 1891. Monday
Went to the Gallery in morning and saw all the pictures, including Dutch.  My favourites are: Venus. Giorgione 2 Paul Veroneses. Sistine Madonna. St George. Dosso Mars and Venus, Garofalo. Madonna Lotto. Two panels Ercole Roberti. Adoration Francia. Dream. Dosso. Justice. Dosso. Portrait of a Man. Titian. Jacob and Rachel. Palma. Santa Conv [ersazione], Palma. Annunciation. Cossa. and many more, too numerous to mention. Paid our last call on Michael Fields at Krankenhauss in the midst of a tremendous thunderstorm. Came back and packed [099] and read Morelli on Munich and Robertson’s Charles V. Discussed local Christianity. B. shaved off his moustache!

Regensberg Sept.  1. 1891.
 Hotel Goldner Kreuz, Regensberg
An old inn. Delightfully large room.
Pleasant journey from Dresden, 8. 45 to 5. 45. Finished Goncourt’s Journal, read Pierre Loti’s “Le Livre de Pitié et de la Mort,”et Villier de Lisle Adam’s “Histoires insolites.”Studied German. Read Charles V. Reached Ratisbon in time for a sunset on bridge over the Danube. Saw Cathedral, which had resemblances to Notre Dame de Paris. Late Gothic but on the whole good - for Gothic! Sent notes on Frankfort to Michael Fields in evening.
[100] Journal des Goncourts.
 IIem Série - II Vol.
10 Jan. 1872. Aujourd’hui, chez le français, le journal a remplacé le catéchisme. Un premier Paris de Machin ou de chose devient un article de foi, que l’abonné accepte avec la même absence de libre examen que chez le catholique d’autrefois trouvait le mystère de la Trinité.
16 Jan. 1872. Rien ne m’agace comme les gens qui vraiment vous supplier de leur faire voir des choses d’art, qu’ils touchent avec mes mains irrespectueuses, qu’ils regardent avec les yeux ennuyés.
1 Sept.  1873. Après une affreuse migraine [101] je rêvais, cette nuit, que je me trouvais dans un endroit vague et indéfini, comme un paysage du sommeil. Là, se mettait à écurie un danseur comique, dont chacune des poses devenait derrière lui, un arbre gardant le dessin ridicule et contorsionné du danseur.
[102] 20 Jan. 1876. Hier soir, dans le fumoir de la princesse, au causait de Rossini, quelqu’un parle d’une lettre écrite par lui à Paganini, le lendemain de sa première audition, lettre dans laquelle le maestro est tout entier. Il lui disait qu’il n’avait pleuré que trois fois dans sa vie: une première fois, lorsqu’il avait eu son premier opéra sifflé; une seconde fois, lorsque, dans un partie avec ses amis, il avait laissé tomber dans le lac de Garde, une dinde truffée; enfin la troisième fois, en l’entendant la veille.
3 Juillet 1870 …il faut pour faire quelque chose de bon littérairement, que tous les sens soient des fenêtres grandes ouvertes.
[103] Goldner Kreuz Ratisbon Wednesday. Sept.  2. 1891. 
Breakfast of grapes and coffee in our sunny bay-window. Went forth to view the town. Were delighted with the quaint portal of the Romanesque Irish Church of XII Century, Die Schottenkirche - Strolled along the Boulevard in Park on old town wall, and came to the Cathedral. Went inside - good proportions, light and gay, with beautiful stained glass. Lets in the real god - the Sun. We saw the treasures – 
Hair of Blessed Virgin 
Spike from Crown of Thorns 
Several inches of wood from True Cross 
(set in gold and jewels, which having been pawned to the Jews of Regensburg, was seized from them and deposited there), 
Brown mummified hand of S. Chrysostom with diamond ring; [104] 
Hand of Innocent massacred at Bethlehem 
Hordes of Bones, etc.
Skeleton of Child in jewels, etc. “found under floor of Jewish Synagogue after the expulsion of the Jews from Regensburg in the XV Century_” (!)
Drove out to the Walhalla (there was a steam tram!) which was startling and surprising. We walked up through a pine forest and came suddenly upon the white Doric columns of the temple flashing in the sunlight. As we walked about it looking at the profilation of the columns and the beautiful view of the plain and the Danube through them, our delight was almost [105] lyrical. The temple itself is really an astonishing bit of architecture, carried out with good taste and unpretentiousness. The lines are perhaps a trifle too rigid, but certainly only inferior to the lines in the Parthenon and the Museum. In proportions, it is very much like the Parthenon, only it looks a little tamer. But, after all, it makes up by being perfectly preserved and “herrlich wie am ersten Tag.” The situation is hardly to be surpassed, and the idea of placing it on a splendid platform against the hillside is magnificent. But it is curious that looked at from below, the wonderful series of stairs leading up to the Temple, look rather too much like the steps let down from a huge carriage. [106] The interior was unexpectedly pleasant, rich, but not over-decorated. Most of the busts are very poor, and the choice of them seems to have been made after a “scheme of his own.” The polychromatic decoration of the Ionic columns and of the Caryatides (Valkyris) was quite likely genuinely Greek, and certainly very agreeable. What a spot! The Temple faces a wide, wide plain, through which winds the blue Danube. On each side smaller hills covered with green pines flank the central one where the Temple stands. The columns in the sunshine looked like Paul Veronese’s marbles. Driving back we saw it rosy with the sunset. A thing not to miss. ☜
[107] Hotel Roth. München. Thursday Sept.  3. 91. 
From Regensberg to Munich 8. 18 - 11. 45. Read Faust all the way. The Pinacothek from 1-2, just a glance at the Italian pictures. How lovely the Francia, and how matchless the Titian. Morelli compares it to the last works of Franz Hals. The Sodoma was delightful, and a small Correggio.
We were both secretly dying [sic] to get to the exhibition of modern French (and other) pictures, so, after a rest, we went to the Glaspalast and found some of our favourites of the Salon, as well as some new ones. Three Monets there, and four or five Manets, besides a new Besnard and two new Dagnau-Bouverets [108] impressed us as wonderful, especially the Monets! Then there was a vast array of Böcklins and Lehnbachs - and any number of Americans, Spanish, Dutch, etc., to which we gave merely a hasty glance. The exhibition closed at 6 and we walked to the Propylaia and sat a long time on the steps of the Glyptothek, discussing the latest Parisian fad, the artistic society of the Rosy Cross founded by San Peladan in the interests of “Beauty”. I found the Besnard sunset disfigured by the pert, grinning girl in the foreground. B. said I would not feel so in ten years. We shall see! (n. b. I came round to his opinion in a day or two!!!!)

[109] Hotel Roth. Munich. Friday September 4. 91.
Went to gallery in morning and looked over the drawings. The only ones of note were the Fra Bartolommeos (especially a Head of a Woman), Mantegna, Madonna with an angel on each side; Sodoma, Virtues driving out Vices (analogous to Mantegna’s picture in the Louvre); some small Cupid pictures by Penni; a Mantegna, and a much destroyed Pollaijuolo. Afterwards we studied the Italian pictures. B. disagrees with Morelli on several points: 1. That the so-called “Lionardo” is not Flemish but Italian, possibly an early Verrocchio. 2. That the so-called Luini is not a Solario. 3. That the Paris Bordone Portrait is not much repainted. 4. [110] That the Moretto is a Moretto, and not a Moroni. Looked at the Dürer engravings.
Afterwards quarrelled slightly and then walked in the Park - 
Hotel Roth. Munich. Saturday Sept.  5 91
We took the 7 o’clock train to Augsburg. I read Faust all the way. Wandered about the town and saw the Cathedral. The stained glass windows of the 11th century mentioned by Baedeker exist only in his imagination. Cathedral filled with altar-pictures by German masters, best seemed to be by Burckmayer. At 9 went to the gallery and looked at the Italian pictures there. The most beautiful was a Tintoretto.
[111] After the gallery we visited the other Churches and looked at the picturesque parts of the town. Then had an excellent lunch at the “Grün Haus” and came back by a slow train, sleeping and reading Villiers de Lisle Adam’s “Le Secret de l’Échafaud.” Tried to re-write Correggio article.

Hotel Roth. Munich. Sunday Sept.  6. 91.
Went to the Pinacothek and studied and noted the Venetian and Veronese paintings. Visited the various Brauereis in the evening, but they were so smoky that even the music did not tempt us to stay. As it was a Volksfest, a cold rain was falling all day. God is evidently as undemocratic here as in England!

[112] Hotel Roth. Munich. Monday Sept.  7. 1891. 
The Gallery in the morning. Florentine, Umbrian and Roman Schools.
Looked at photographs at Hanfstaingl’s. Visited the Schack gallery and enjoyed Lenbach’s admirable copy of Titian’s Charles V on horseback. Saw some Böcklins. Went to the Glyptoteck. B. enjoyed the Augustan Marbles more than even before. He found them delightful as sincere studies in anatomy. Went to the International Exhibition and saw the French pictures - three inexpressibly delightful Monets: a lake at sunset, the sea and cliffs, painted in ’82, and fields in summer. Five Besnards, of which two were marvels of poetry and light: a girl standing by the sea at sunset, and a naked [113] boy sitting by a blue mountain lake.
3 Dagnau-Bouverets, A Madonna and Child, a study in the reflection of green leaves and sunlight upon a white dress, a small landscape and a woman sitting in the open air. 1 Whistler, painted in ’66! ships and sea in twilight. 3 Meissoniers, painted in ‘’55. A Detaille almost as good. 2 Bonnats, the Samson of this year’s Salon, and an Italian child. 5 Manets. Several of Millets, Troyon, Daubigny, Corot, Diaz, Hamel Jacques, etc. Some deliciously decorative Ribarz, Dagnaux, Breslau, Ribot, Hagborg, Meunier, Stéveres, Israels, Mesdag, Roederstein, Agache, Dinet, Blanche, L’Hermitte, Courtois, Gervex, Puvis de Chavannes, Dupré, and many others were represented. We [114] enjoyed Monet, Manet, and Besnard most of all. We also looked at Böcklin and his school. It was worth coming to Munich if to see nothing but the Monets. After the Exhibition, we went back to Haufstängl’s and bought some photographs. Then came back, and while I read Faust, B. wrote a few pages about the Augustan marbles - which I criticised savagely before going to dinner.
Tuesday Sept. 9 [8]. 1891. Munich – Verona
Milanese and Ferrarese Schools in the Gallery in the morning. B. lunched with Mr. Marshall. I read Charles V and packed. Went to the International Exhibition in the afternoon. On the whole, we liked best the Besnard sunset over the water.[115] Took the night train to Verona. Read Richepin, “Quatre petits Romans.”

Wednesday Sept.  10 [9] 1891. Colombe d’Or Verona
Embankment broken, so we had to change cars at 5. 30, walking a long way. The scenery was very fine. At Ala we found our train had gone on and we had 4 hours, so we went to a hotel in the town and had breakfast and a sleep. Reached Verona at 4. 20. Walked to San Zeno and saw the cloisters. Took a stroll after dinner.

Thursday Sept.  11 [10]. 1891. Verona
In the morning (8. 30-12) went to San Lorenzo, Santi Apostoli, Santa Euphemia, Santa Anastasia, the Duomo, and San [116] Giorgio in Braida. After lunch and a rest, went to the Gallery and then to San Bernardino and came home by the Porta Palio.
Complete overwhelming of me, and discouraging of B. After such galleries as London and Berlin and Paris and Dresden, the pictures here seemed poor to him, and he confessed to preferring the copies in San Bernardino to the original Cavazzuolas in the Museo!! The architecture impresses me more than the pictures. There is so much beautiful colour about everything.
Read Charles V, studied German. B. “got up” Verona from Morelli, etc., etc.

[117] Friday Sept.  12 [11]. 91 Hotel Colomba d’Oro. Verona.
Went to San Niccolo, Santa Maria della Scala, San Nazaro e Celso, Santa Maria in Paradiso, San Tommaso, San Fermo, San Paolo in the morning. Enjoyed especially the Montagnas in San Nazaro and the Buonsignori and Paolo Veronese in San Paolo. In the afternoon in Santa Maria del Organo, where I recognized the Savoldo, to my delight, and where B. began to shake off the trail of his travels among German galleries and to enjoy the Veronese themselves.
He wrote to Prof. Bôcher:
“… In Italy the pictures must be looked at in their frames, for as painting merely they are sometimes not worthwhile. At any rate that was my first impression in the gallery yesterday. Most of [118] pictures looked ruined and repainted and a trifle provincial into the bargain. The fact is one wants a pair of fresh eyes for every school of painting, that is one reason why it is so hard to get to know Italian pictures in Transalpine Galleries. There the temptation is overwhelming to study all the school at once, and through spectacles fit for none. In Verona, you are confined to one School. Before you can appreciate the pictures here, you must be penetrated with the feeling that you are in Verona and nowhere else. You must realize the biological necessity for the painters to paint precisely as they have done. Perhaps it may sound strange to speak of biological necessity in connection with anything like the fine arts. But as far as I know [119] all art criticism tries to account for what man does in the arts, just as the zoologists account for beavers building dams, or birds building nests. Only criticism continually contradicts itself. It exists because it claims to be able to reduce the phenomena of the arts to general categories, yet it puts up the dogma that caprice is perhaps all there is in genius.” * Sunset in the Giardino Giusti.
Saturday Sept. 12. 91. Hotel Colomba d’Oro Verona
Went to Santa Trinita and saw frescoes by Brusasorci. Then to San Bernardino, where I was overcome by such a feeling of illness that I had to come back, and lie down all the rest of the day with diarrhea and nettle-rash. I read Mrs. Green’s “Henry II. B. studied his “bibles” very conscientiously.

[120] Sunday Sept. 13. 91 Hotel Colombe d’Or Verona
Went to the Gallery in the morning - but I was almost too ill to see anything. However, I enjoyed the Cavazzolaswhile B. studied his problems. Lay down the rest of the day, feeling pretty ill. B. went to San Stefano, the Duomo, San Siro e Libera, Santa Maria in Organo, Santa Chiara, and San Giovanni in Valle. I read Prescott’s “Ferdinand and Isabella”-and wrote to Evalyne. Went to see fire-works in the Amphitheatre.
Monday Sept. 14. ‘91
Went to San Stefano and studied the Brusasorci frescoes. Then to Santa Maria in Organo - where we met the Sacristan whom B. liked so much a year and a half ago. He took us in the afternoon out to a Church on a hill about 8 kilometers away in a little [121] village called Marcellise. There we discovered four fine Girolamo dei Libris. On the way back we stopped at a beautiful round church built by Sanmichele, called La Madonna della Campagna. There was a fine Farinati and some old frescoes inside, but the architecture was more wonderful than all!

Tuesday Sept. 15. 1891. Verona.
Went to Palazzo Canossa, the decoration of the Ball Room by Tiepolo - Then to see the frescoes by Brusasorci in the Palazzo Ridolfi. Went to San Lorenzo and Santi Apostoli and to San Fermo. Gallery in afternoon.

[122] Wednesday Sept. 16. 1891. Verona
Went to Mantua by 7 o’clock train - Read Heine and German guide book and Two Gentlemen of Verona on the way (1 1/2 hours). Saw St. Andrea, built by Alberti, with Mantegna’s mortuary chapel. Saw Duomo, an old Church made over by Giulio Romano. Saw Santa Barbara and the Gonzaga Palace and Mantegna’s frescoes, and remarked the difference between Cavenaghi’s restorations and the others. Afterlunch saw 2 Buonsignoris in the Accademia Vergilia[na], and saw the Palazzo del Te, built and decorated by Giulio Romano.
Took 2 o’clock train back, and [123] went to Gallery, where we worked till 6. Bernhardwrote about Giulio Romano in the evening.

Thursday Sept. 17. 91. Verona.
Went to S. Eufemia, the Bishop’s Palace and S. Bernardino to take notes in the morning. A letter from Gertrudedecided me to go to Florence next week. Finished notes of San Fermo and Museo in the afternoon. Wrote to “Michael Field” - Quarrelled.

Friday Sept. 18. 91. Hotel Città di Monaco. Venice
Spent the morning in San Paolo, San Nazzaro e Celso and San Tomaso and climbed up by the ladder to the platform constructed for repairs before the Pisanello [124] fresco in Sant’Anastasia. We spent all our time there, face to face with it, till it was time for the 4. 20 train to Venice. Read Isabellaand Charles V,German in the train. Arrived in Venice - !! - sunset – moonrise time. Walked in the Piazza and had a gondola ride after dinner.

Saturday Sept.  19. 91. Hotel Monaco. Venice
Went to St Mark’s, San Zaccharia (Bellini), Santa Maria Formosa (Palma), San Giovanni e Paolo (Lombardi) before luncheon. After went to Layard’s and took notes for 2 1/2 hours. Revised Correggio article in evening.

[125] Sunday Sept.  20. 91. Hotel Monaco. Venice.
Went to Layard’s 8. 30 and finished our Catalogue at 11 and went for an hour to the Doge’s palace. After luncheon tried in vain to see various churches, all of which were closed or too dark - but we had several steam-boat rides on the Grand Canal. Wrote Correggio after dinner.

Monday Sept.  21. 91. Venice
Went to the Salute and took notes and to the Seminario in the morning.
To the Accademia in the afternoon and towards evening hung about the Doge’s palace examining the capitols and sculptures, etc. Discussed Jesuitism and Oxford.
Tuesday. Sept. 22. ’91 Venice -
San Polo and the Frari in morning. Scuola and Chiesa di San Rocco in afternoon. Went to the Lido where I had a swim. Correggio in evening.

[126] Sunday Sept. 27 ’91. Hotel Monaco. Venice.
I arrived from Florence at 11. 30 last night. This morning we met Costa and went to the Correr. After lunch B. and I went to the Giovanelli palace and saw the pictures. Then I went to sleep while B. and Costa went to the Lido and took a long walk, discussing pictures – among other matters, the influence of Dürer upon Lotto. B. and I talked much all day about Gertrude Burton with whom I stayed in Florence.

Monday Sept. 28. ’91. Hotel Monaco. Venice
Went to S. Maria Mater Domini (Catena, Tintoretto), St. Cassiano (Tintoretto), S. Giovanni Elimosinario (Pordenone, Titian) in the morning. After luncheon joined Costa at the Accademia, and when that closed went to Murano and saw the Cathedral and another Church there, and came back at sunset. The picture I enjoyed the most was the one Titian painted when he was 99. It was not quite finished by him, but there is enough left. The Tintorettos, too, were very enjoyable. B. began to read Ruskin. It puts [127] him in a rage. Indeed it is quite impossible to see why he is said to have a good style.

Tuesday - September 29. 1891. 
Met Costa at the Salute at 9. Then to the Redentore - Canon Farrar was at the Salute reading Hare to an admiring group. After that we went to San Sebastiano and then to the Carmine. In the afternoon we met Costa again at the Scuola di San Rocco and spent several hours there enraging ourselves over Ruskin’s astonishing criticisms. Then to the Church of San Rocco, and then we had a beautiful hour at sunset in the Giudecca.

Wednesday Sept. 30. 91. Venice
Met Costa at San Giorgio in Bragora and then went to San Francesco della Vigna, San Antonio and San Giovanni e Polo. Immediately after lunch we started in a [128] gondola with Costa and his brother to Torcello, which was enchanting - and to Burano, where we had great fun with the children. The boatmen lost the way coming home so that we were rather late.

Thursday Oct. 1. Hotel Murano  Venice
I was tired, and unhappy - B. went alone to the Correr - with Costa. In the afternoon I had a swim in the Lagoon and we went to S. Giorgio Maggiore. What magnificent architecture! and Ruskin says it “is not worth a moment’s notice”-!We read Villiers de l’Isle Adam, “Nouveaux Contes Cruels” and “La Révolte” - also a Russian Priest by Potapenko. B. went to the Piazza and met Costa who had an article by Claude Phillipps on Morelli, good in manner but poor in matter.
X X X
[129] Friday Oct. 2. 91. Venice.
Met Costa in S. Giuliano - then went to San Salvadore (where they had a quarrel with the priest!), San Bartolomeo Rialto, S. Giovanni Crisostomo, and S. Lio. In the afternoon we met in the Ducal Palace and then to San Giorgio Maggiore and to S. Pietro in Castello and came home in a gondola by the Lido. In the evening we began our INDEX!!

Saturday Oct. 3. ‘91. Venice.
Met Costa [at] Santa Maria Formosa - went to San Felice and Santa Maria in Orto - After lunch, to the Academy and then to look at a reported Lotto and a horrible private collection. It was dark and rainy and we had tea at Florian’s. Then B and I worked at an Index for two hours, and then wrote to our mothers.
[130] Sunday Oct.  4 91. Venice
Met Costa at the Doge’s palace and studied the Tintorettos and Bassanos and the false Paul Veroneses. In the afternoon we finished our great “Repertorio di Quadri Italiani” and read Villiers de Lisle Adam, and took a walk in the Public Garden, discussing education.

Monday Oct. 5. 91 Hotel Monaco Venice
Went to Santa Maria della Pietà, S. Francesco della Vigna, and San Matteo in the morning. Felt tired and went out to the Lido and had a good walk. I had a swim au naturel. The sea and sky were perfect. Read “Axël” by Villiers de l’Isle Adamand Richepin’s “Morts Bizarres” and Venturi’s paper on the School of Modena.

[131] Tuesday Oct. 6. ‘91 Venice
Went to S. Moisè, Santa Maria Zobenigo, S. Stefano, S. Vitale, Gesuati, S. Trovaso, S. Sebastiano. In the afternoon to St. Mark’s and then out to the Lido where I had a swim.

Wednesday Oct. 7. 91 Venice
Spent the morning at the Accademia, and the afternoon in S. Zaccharia and Giovanni e Paolo. Went to the Piazza in the evening and heard the band play “Carmen –“

Thursday Oct. 8. 1891. Venice
Met Costa at S. Pantaleone and after studying the Antonio di Murano there went in to the Carmine. There in the absence of the sacristan, I cleaned the lower part of the Lotto from the dust and [132] cobweb and candle-grease of ages. The sacristan appeared enraged when he caught me. He said the picture belonged to the Academy and no one was allowed to touch it. Presently - to my intense surprise - he invited us to come tomorrow and wash it - saying he would supply the water and sponge and ladder. We went on to S. Barnabà and S. Trovaso and then came back to lunch. After lunch we went to S. Giovanni e Paolo, taking the Buonsignori photographs, and we were all convinced that the altar-piece there is by him. Then we went to San Marco and saw the organ shutters by Gentile Bellini in the work-shop and the bronze doors, and then had tea at [133] Florian’s. It was raining so we came back and worked at our Repertorio -

Friday Oct. 9. 91. Hotel Monaco. Venice
Academy with Costa in the morning. In the afternoon cleaned the Lotto in the Carmine with water and turpentine and knives. It turned out to be very beautiful, especially the landscape, one of Lotto’s finest. Costa also gave the Carpaccio a washing. Then we floated about in a gondola.

Saturday Oct. 10. 91. Venice
A photo of Ray came in the morning. We went to San Spirito and the Gesuati and then 2 hours at the Academy. Then to the Scalzi and San Giobbe where we enjoyed the Savoldo. In the afternoon we went to the Lido where I had a delicious swim.
[134] Sunday Oct. 11. 1891. Hotel Monaco. Venice
Went to S. Marcuola, and S. Marziale, and then to the Correr. There 
we met Mlle Miranda and the Costas, who were charming, but who interfered with our work. Went with them to the Palazzo Reale in the afternoon, and then with Costa to the Querini Stampalia. Afterwards we took our gondolier (58) and rowed about in the sunset. In the evening B. went to call on Mallele Jackowska and Mlle Mercier. Read “Contes Cruels” and Symonds and Howells on Venice. They are almost worse than nothing. One gets very tired of Howells’ American drollery and “stuffing”, for his book has no real matter. Symonds [135] is not drool, but he is sentimental, which is worse.

Monday Oct. 12. 91. Venice
Met Costa and went over the Royal Palace, where we found, among other things, 2 glorious Tintorettos, and one of Titian’s loveliest things, a decorative ceiling painting in the Libreria, painted when he was 93. Then we went to S. Giorgio Maggiore and Santa Maria delle Zitelle. I was tired after lunch and rested. Then went to see Pordenone’s frescoes in the cloister of S. Stefano - done by him in rivalry with Titian, so Howells says, when they were both in love with Palma’s lovely daughter Violante!! Read Gray aloud, and then B. went to call on Mlle Jackowska.
Finished Contes Cruels, like them less than others.
[136] Tuesday Oct. 13. 91. Hotel Monaco. Venice
Went in the morning with Costa to the Correr, and took the Bellini photographs to compare. After luncheon went to the American Consul’s and got my permit to go to the Galleries. It was pouring. We went to Florian’s where B. read Gebhardt’s article in the Revue de Deux Mondes called “L’état d’une âme a l’an 1000.”Read Shakespeare in evening and finished notes. Began “L’Ève future.”B. finished “Dans l’Inde” by Chevrillon.

Wednesday Oct. 14. ‘91 Venice
Academy in the morning - met Costa. Ducal Palace after luncheon and then went on the lagoons with Costa and discussed English poetry and Tolstoi. Finished L’Ève future, to be compared to a Jules Verne. Began Mrs. Oliphant’s “Makers of Venice”.

[137] Thursday Oct. 15. 1891 Venice
[in Bernhard’s hand:]
Between the Irish and the rest of the population in the U. S. particularly in the Eastern States it is bound to come to a war before fifty years are over.
[in Mary’s hand:]
Academy in the morning. In the afternoon went with Costa to the Palazzo Sina the stair-case of which is decorated with wonderful frescoes by Pietro Longhi, of most delicious genre, Venetian “highlife”, in the wigs and powder of the day. Then we went to the Palazzo Rezzonico (just opposite) and saw the ceiling painted by Tiepolo. It belongs to Browning’s son and his wife, and they have furnished it in exquisite taste. Went out on the Giudecca.

[138] Friday Oct. 16. 1891. Hotel Monaco Venice
Went to S. Giorgio dei [sic] Schiavoni and took full notes. The light was splendid between 10 and 12. 30, in spite of Ruskin!Quarrelled dreadfully and B. went alone to the Ducal Palace. Then he came back for me, and we went with Costa to see Sir Henry Layard’s pictures again, and then to Guggenheim’s, to see the Tura - Moonlight and gondola in the evening. I recited Matthew Arnold and Renan.

Saturday Oct. 17. ’91. Venice
Went to San Trovaso and San Sebastiano. At 2 Costa called for us and we went to Santa Catharina, then to San Michele (Campo Santo) to see a picture Loeser described as a Savoldo, but which turned out to be a bad XVIII century picture. Then to San Donato Murano. I went to call on Miss Bliss and B. to call on Mlle. Jackowska and Mlle. Mercier. I finished Mrs. Oliphant’s “Makers of Venice”. B. read Horatio Brown’s “Venetian Studies.”

[139] * Sunday Oct. 18. 1891. Venice
B. took Mlles Jackowska and Mercier to the Academy. Mlle Mercier told him about a new varnish or rather glaze for pictures which she had invented. I took Miss Bliss to San Marco, S. Giorgio Maggiore, the Salute and the Academy. In the afternoon we lounged at Florian’s, walked, went up the Campanile and wrote. In the evening we wrote and I began “Dans l’Inde” by André Chevrillon. B. read Horatio Brown.

Monday Oct. 19. 1891. Venice
Went in the morning to S. Silvestro, S. Giovanni Elemosinario, S. Maria Mater Domini, Giacomo in Orio, S. Simone Profeta, Palazzo Labia and Correr. It rained and we lost an umbrella and B. got wet through. Doge’s Palace in the afternoon. Then we went to see Costa’s photos at his hotel. Finished Dans l’Inde.

[140] * Tuesday Oct. 19 [20]. 1891. Hotel Monaco. Venice
Went to S. Giuseppe di Castello and the Correr. Afternoon Doge’s Palace with Costa, where we called upon Signor Barozzi and found a Buonsignori hanging in his room. He let us see the Titian fresco of St. Christopher. Then we went to Santa [Maria della] Fava and saw a Tiepolo. Wrote in the evening. Read “Venetian Studies” by Horatio Brown.

* Wednesday Oct. 20 [21]. ’91. Venice
Went to St. Fantino - Atheneo Veneto - S. Gallo - S. Salvador[e], S. Giovanni Crisostomo, S. Canciano, S. Maria dei Miracoli – Gesuiti - S. Luca. After lunch with Costa and his brother to the Giovanelli collection, then tea in the Piazza where we discussed going to Vacina. In the evening took Miss Bliss to the Piazza.

[141] Thursday Oct. 21 [22]. 91, Venice
I was ill, but went for a while to the Academy. Came home and read “Venetian Studies”-Rested in the afternoon and wrote. B. called on Mlle Jackowska.
* Friday Oct. 22 [23]. Venice
Went to Ducal Palace in morning, and to the Scuola di S. Rocco in the afternoon. Then I went to the Frari while B. went with Mlle Jackowska to see the paintings of a certain Swiss Baron. He was well bored. I walked back with Costa along the Giudecca and discussed Sebastiano del Piombo and the great books B. is to write. Wrote and looked at photos in the evening.

Saturday Oct. 23 [24]. 91 
Finished our notes on the Ducal Palace, and then went to S. Giuliano and then met Costa at S. Giovanni Crisostomo. Then B. went to S. Simeone to see if the ‘Trinity’ there was by Catena or Benedetto Diana. [142] He decided it was Catena - under Botti’s repaint!He met Costa and me at S. Cassiano. In the afternoon we all went to the Frari. I read Barbey d’Aurevilly’s “Les Diaboliques”. B. finished Bourget’s “Sensations d’Italie” - par un homme qui n’a pas de sensorium.

Sunday Oct. 25. 1891. Hotel Croce d’Oro  Padua
Went to the Academy for a last look in the morning. Met the two Costas and arranged to go to Vienna on the 5th. Last look at St. Mark’s - We came in the 4 o’clock train to Padua and walked a little in the town before dinner and then spent the evening reading guide-books, etc., in preparation for our work here.

[143] Monday Oct. 26. 1891. Padua
We spent the morning in the Chapel of the Arena, which is filled with Giotto’s frescoes. We were thoroughly surprised by the real beauty of all the compositions, by the delightful straight-forwardness and clearness of his stories and real appropriateness of his allegories. But we were even more struck by the real beauty of the frescoes as painting - the wonderful purity of the outlines and the daintiness yet richness of the colouring – and perhaps more than anything else – what is so rare in the old Masters – the sweep of his brush. Almost every stroke of this can be traced – and it shows a masterly skill and decision. The naïveté is 
[144]

very winning – and coupled with this is a delicious gaucherie, remarkably like that gaucherie which we also find in Japanese art. In a curious way his peasants, even to their clothes, and his way of treating landscape and animals, is also Japanese. Giotto as well as the Japanese looked upon a picture as the means of expressing one idea – so they mentally abbreviate the scene – simplify it. From one point of view, of course – the point of view of atmosphere – these pictures are as much bas-reliefs as if they were in marble – and this [145] very simplicity is a quality which Giotto has in common with the bas-relief. This is simply saying that Giotto had not yet got free from the style of painting which was nothing but the Alexandrine bas-relief in paint. Certain things in these frescoes are types for the whole school – as, for instance, arranging the heads in a line – which is found throughout the whole Tuscan school - The sleeping soldiers and the resurrection may have been in Mantegna’s mind when he painted his Resurrection, and the composition of the Baptism is certainly identical with Bellini’s and Cima’s.[146] Afterwards, we went to the Scuola d[e]i Carmini - and after luncheon to the Gallery and the Church of St. Antony, and then took a walk on the walls. Letters came from “Michael Field” in the evening, and we annotated the Louvre Catalogue for Logan.
Tuesday Oct. 27 Hotel Croce d’Oro Padua
Went to Duomo and Bishop’s Palace and discovered Montagnana!Then to Santa Maria in Vanzo, then Sanmichele. In the afternoon we finished our notes on the Gallery and went to the Scuola del Santo.

[147] Wednesday Oct. 28. ‘91 Padua
Got up at 4-30 and took the train at 5-30 for Monselice - where we spent the hour we had to wait in exploring the town. It was a great surprise. From the station one only sees the ruined medieval castle, but as one wanders into the town and climbs the hill a little way, a most wonderful view opens out, with the conical peaks of the Euganeans rising opposite, and the plain stretching on endlessly. The effect somehow was very much like that of a South Italian landscape, perhaps due to the volcanic hills. Only palms [148] were necessary to make you believe you were in Sicily or Naples. Lower down in the town there is a sort of decaying renaissance castle, and from the castle a road winds along the hillside broadening out into terraces and lined on the hillside with baroque chapels, all finally ending in a delicious baroque villa with its own little baroque church. We rarely have had such a complete impression of a past and yet comprehensible phase of human existence.
From Monselice we went on to Montagnara – passing – so reluctantly! – Este on the way. Montagnana, too, was a happy surprise. Baedeker says well that its completely preserved town walls [149] are alone worth a visit. At the corners are towers, of which Cima or Carpaccio’s most wild dreams of fortifications are not too wild. But so picturesque, so quaint, so really beautiful, with the circle of lines and the broad grassy moat, with the narrow stream of water with the women washing and the geese and turkeys and donkeys cropping the grass. Then we found Buonconsiglio in his glory!
After Montagnana we went to Rovigo, but I draw a veil, for the gallery there was a fraud., the town was not pretty - our train did not start till after 8 - and we were [150] both poisoned by something we ate, copper-poisoned, I think.

Thursday Oct. 29. ’91. Croce d’Oro. Padova
Went to Santa Giustina in the morning and climbed up close to where we could see the Paolo, such a marvelous thing. We were both sick and dizzy from our poisoning, but we kept on and “did” the Scuola del Santo and the Church of S. Antonio. After lunch we went to the Capello [sic] di San Giorgio and enjoyed the wonderful Altichieris - in spite of the bitter, piercing cold, which suddenly took the place of the [151] fine, mild weather. The last part of the afternoon we spent in the Eremitani before the Mantegna frescoes. B. was awfully sick in the night.

Friday Oct. 30. ‘91 Padua.
We spent the day at Vicenza, but did not have time to enjoy Palladio very much, because there were so many pictures to be seen. It was a day to be remembered by me, because I first became aware of Mantegna as a really great painter - There was also a fine Buonconsiglio [152] We were not able to see the Loschi Giorgione, unfortunately, nor to get to Monte Berico. It left me with a longing to go back, and to make acquaintance with the stately palaces. The finest building of all seemed to be the one in which the pictures are collected.

Saturday Oct. 31. ’91 Hotel della Spada Castelfranco.
An early train took us to Bassano, where we spent the morning imbibing Bassanesque views [153] outside and the Bassanis painting in the churches and gallery. There is very little in the churches, but the gallery is delightful. No gallery is better lighted, or with a nicer custode, and in the long room there is scarcely anything that is rubbish. Jacopo Bassano has nearly 20 pictures there, many of them among his very, very best. We saw Ruskin’s and Browning’s signatures in the visitors’ book. But the astonishing thing was the look of the town [154] and the people - It was market day, and the “usual” Bassano was being enacted at every corner, cows and oxen, and copper pots and pans, and carts, and vegetables, and brightly dressed men and women bending over. It is really impossible to understand the Bassani without coming here, especially Jacopo.
Later we came to Castelfranco, and got just a glimpse of Giorgione’s Madonna before sunset. What a sunset – glowing long and long, like an American sunset, as we walked round the walls of the tiny town.
[155] Sunday. All Souls’ Day. ‘ 91Albergo della Spada Castelfranco
What happiness to wake up in such a place! For once the early church bells were enchanting – and we got up early and saw the gleam of dawn strike on the distant campanile – almost as graceful as St. Mark’s, and on the square tower with the baroque cupola, which “defying all laws of propriety”- makes its chief beauty, on the blue green moat around the old wall, reflecting the towns, and on the statue of the young Giorgione himself who stands on a little island in the moat, his pencil and book always in his hand, a gay young cavalier, in fashionable clothes. If the statue were as beautiful as its surroundings, it would leave nothing to be desired. Even as it is, the poetry [156] that Giorgione casts over everything, near and far, that in any way touches him, has not left his statue bare of charm. The place itself is even more ‘Giorgionesque’ than Bassano is ‘Bassanesque’. Everywhere beautiful peasants, with something of the charm of his faces, the simple square towers he loved to paint, the wide stretches of sky and tender trees against it. Brought up in such a simple, beautiful town, his eye was trained to love simple lines of architecture - and what a blessing for the whole train of his followers.
Later We spent an hour and a half with 
[157]

 the Madonna - on a ladder, with a good light. How I enjoyed it! Unromantic as it sounds, I enjoyed her red robe falling across her lap, and her green tunic, the most of everything in the picture! They are not repainted at all, and how beautiful the lines of the drapery are, like the clear, nervous lines of sensitive orchid petals.
Then we went to Treviso and spent most of the afternoon in front of the Savoldo alter-piece in San Niccolo. We also got a glimpse of the Titian and Pordenone in the Duomo. I was ill from the Rovigo poisoning, but I enjoyed myself.
[158] Monday Nov. 2. ‘91, Stella d’Oro. Treviso
I was so ill that we decided to drive, and we went out to S. Cristina and saw the interesting Lotto there. Then we saw the false Giorgione in the Monte di Pietà, and after luncheon we went to Motta di Livenza. We saw a beautiful, most uniquely quiet little spot - with a delightful Church out of the town, approached by an avenue beside a stream. The picture there is a puzzle – is it Savoldo or Pordenone??Then we saw the Scarpa Gallery, and enjoyed some of the pictures immensely. We had dinner in the kitchen of a little inn, with the MOST BEAUTIFUL Giorgionesque hostess!!!! [159] The settle running all round the deep fire-place, and the country yokels who came in and sat there in the shadow of the chimney with the firelight on their faces - made an indescribably enjoyable ‘genre’ picture.

Tuesday Nov. 3. ’91. Italia - Udine
In the morning we saw several churches and finished the notes on the cathedral.
Then we came to Pordenone and saw his pictures in the Duomo and the town hall, and then came here.
Wednesday Nov. 4. ‘91 Udine
Visited the pictures - What a charming town, an inland, small copy of Venice, the town hall ever prettier than the Doge’s Palace. At sunset we climbed to the castle in the site of Attila’s strong hold - and saw the [160] circle of mountains and the sunny plain. How beautiful it was!! Bernhard thought of nothing all day but Giovanni, Martini, and Girolamo da Udine, and which, if any or all was or were Pellegrino di San Daniele - The problem remains unanswered!!

Thursday Nov. 5. ’91. Vienna. Hotel Tegetthof
We met the Costas on the train at 7. 50 and came on to Vienna, reaching it at 9. 30. The carriages were comfortable and the scenery marvellous, and we enjoyed ourselves very much. We read Villiers de l’Isle Adam’s “Nouveau Monde”and Flaubert’s “Trois Contes”. Giovanni had sweets, which served to beguile the journey.

[161] * Friday Nov. 6. ‘91 Pension Lejeune, Maximilianplatz 4 Vienna
We found nice rooms here taken for us all -Then we went to the Museum - !
x x x x x x x x x
“Faster, faster
O Circe goddess,
Let the wild thronging train,
The bright procession
Of eddying forms
Sweep through my soul.”
x x x x x x x x x
I had a nice long talk with Janet Morison in the afternoon.
Saturday Nov. 7. ’91. Vienna
At home with a dreadful cold. B. and Costa went to call on Wyckhoff. [sic]
Sunday Nov. 8. ’91. Vienna
Cold worse. Could not use eyes. Janet to call.
[162] Monday Nov. 9. ‘91 Pension Lejeune Maximilianplatz 4 Vienna
Cold impossible - but it had to be endured. Costa and B. studied Titian at the Gallery.
Janet came to tea and stayed for a little talk, in which Berenson compared the Jesuits’ way of roc[o]cofying the different architectures, so that they all came out alike, to their way of treating human characters. Janet appeared horrified at the idea of frankly enjoying people like pictures.
Tuesday Nov. 10. ‘91 Vienna
We went to the Lichtenstein. I enjoyed most the Franz Hals - and the Verocchio and also the Savoldo. But it was very cold and I felt ill. I started to go home alone, but lost my way and had to come back, and was, I am sorry to say, horribly cross. It made me unhappy. Tea with Janet. Wickhoff called. Read Goncourt’s Journal.

[163] Wednesday Nov. 11. ’91. Vienna
Went to the Museum in the morning - 10-1. 15 and rested in the afternoon till Janet came to tea, when we looked at Giorgione, Titian and Palma photographs. Did not feel well and had horrible dreams. Read Macbeth.

Thursday Nov. 12. ‘91 Vienna
We went first to the Czërnin gallery, and enjoyed the Ver Meer van Delft. What a wonderful picture!Then we went to the Albertina - where I met Mr. and Mrs. Pennell. Mr. Pennell had narrowly escaped transportation to Siberia, and his hair was all turned white.
We looked at the Venetian drawings, but found very little In the evening we went to hear “Manon”.

[164] Friday Nov. 13. ‘91. Pensione Lejeune. Vienna
Gallery - called on Herr Hofrath von Enghert, Director.
*Saturday Nov. 14. ‘91
Got in by myself and spent hours alone in the Gallery - and enjoyed myself beyond words. “Bleib – du bist so schön!!!”Tea with Janet.

Sunday Nov. 15. ‘91
Finished notes at Academy. Went to Richter concert.

[concert programme pasted down]

Went to drive with Giovanni Costa in the Prater. Janet to tea.

[165] *Monday Nov. 16. 91.
Gallery. Walked together afternoon. Finished Goncourt’s Journal. B reading Crowe and Cavalcaselle’s “Titian.” Tea with Janet.

Tuesday Nov. 17. 91
Special entrance to gallery. Herr Prof. Wyckhoff joined us and took up much valuable time. Began (both) La femme de [au] XVIII siècle. (Goncourts) Began article.

Wednesday Nov. 18. 1891
Gallery. Showed Janet and Mrs. Jägar the pictures. Wrote article.

Thursday Nov. 19. ‘91
Finished and posted article on gallery for Pall Mall Gazette. Went to the gallery from 1-4. Read a French translation (excellent) of “Hedda Gabler” (Ibsen) in the evening. Quarrelled.
* Friday Nov. 20. 91
Great unhappiness at the prospect of going back to London -----!Gallery in the morning. Saw the Greek bronze. Showed pictures to Miss Cooke. Walked in the afternoon. Thought of doing work for the Home Reading Room.

Saturday Nov. 21. 91
We spent the morning at the Albertina looking at the drawing of the “Roman School”- but discovered, among the [166] hundred or more so-called Michelangelos and other great names, very, very little worth looking at, perhaps one of the “school” of Andrea del Sarto and some Baccio Bandinellis. In the afternoon we walked, and Janet came to tea. Finished “La Femme au XVIII siècle”.

Sunday Nov. 22. 1891, Pension Lejeune Maximilianplatz 4 Vienna
I went to the gallery alone while the other went to the Academy. Met Napier Myles in the crowd coming out. Read A. L. Burd’s “Machiavelli” to B. who had a headache. Lord Acton’s Introduction was interesting. Read Richepin’s “Cauchemars”and “Les Soeurs Hédouin”, which is really very good. by Mélandri.
 
*Monday Nov. 23. 1891 Vienna
Went to the gallery. Napier Myles was there, and a deadly mixture of vanity and [167] philanthropy made me waste two valuable hours upon him. He was très embêtant, and cast a dreadful gloom over me. His state of mind – that of a man “trained” at Oxford in literary traditions puffed out with arrogance, catching the trail of a new science and contending with it, and thinking that of course, as an Oxford man, he must understand it! – was amusing; but a little goes a long way! He was particularly anxious to be assured that Morelli really was the latest thing, and that he was “recognized” – but a Fiji islander would have found it as easy to understand what Morelli was [165 bis] about. It made me sad.
Miss Cooke and Mrs. Clarke, whom I took around the gallery on Sunday, were very much struck by the likeness of the youngest man in Giorgione’s Three Astrologers to Bernhard, and also by certain nuances of likeness in the St. Sebastian attributed to Correggio. It is very curious. Giorgione’s Shepherd at Hampton Court looked so like him, and the young man in the Three Ages, and the Portrait by Botticelli in the Louvre. Miss Cooke’s “favourites” are the St. Sebastian and “das grosse Eccehomobild” by Titian. Mrs. Clarke liked Correggio’s Ganymede best.
I took tea with Janet. She is in a curious state of mind. She is naturally an intellectual but she has tried too much to squeeze [165 ter] herself into a moral mould, and the result is a painful contortion, and she doesn’t know where she is. She is shocking by dependence. She wants some one to tell her what to think, but when they tell her, she grows stiff and angry if the thoughts don’t fit into her perfectly narrow and impossible moral mould. So she is unhappy and undecided, enjoying nothing, useless, except as her husband’s “helpmeet”. Her sister who is here is in love with a man younger than herself, and Janet was in a rage over it. She thought it so “low” and “degrading” and utterly incomprehensible, not “ideal” in it.
Women, women? Why shouldn’t a woman love a man younger than herself? Janet’s remark was so characteristic. “I can easily imagine falling in love with a man 50 years old. He would represent all my ideals.” “Falling in love with your head”, I replied, and it made her angry, I fear.
In the evening we read Ibsen’s Fest auf Solhaug.

[168] Tuesday Nov. 24. ‘91 Pension Lejeune Vienna
Went to the Albertina in the morning and while B. and Costa took notes on the Italian pictures exposed, I looked at the Dürers. In the afternoon we walked, and in the evening went to the Burgtheater to see Ibsen’s “Fest auf Solhaug”- It is one of the most charmingly poetic things I ever read, all the way through like a single simple but kinder ballad. It was acted as only Germans can act tragedy! ---!! B. said he used to blame the German actors, but now he sees it is the German public who heave atrociously bad taste, and he goes as to a Chinese theatre for a study of local taste - not for enjoyment of art. I believe they excel in comedy, and indeed the only part in this play well done was the semi-buffoon of a husband.

[169] *Wednesday Nov. 25. ‘91 Vienna
Went to the gallery in the morning and called on two of the directors. Herr Frümel was a pleasant little man, embarrassing in his shyness, but very kind and helpful. He spoke excellent literary French, rather slowly, as if he were turning over the leaves of the dictionary in his head. We saw an unexposed picture, a large Adoration of the Magi, by Jacopo and his son Francesco Bassano. In the evening we quarrelled because B. wouldn’t write, but finally we began an article on the galleries in the smaller towns near Venice.

Thursday Nov. 26. ‘91 Vienna
Called again on Herr Frümel and saw some of the lower rooms - A beautiful small relief by Moderna pleased me more than can be expressed. After a “Thanksgiving Turkey” B. and I went again to the Gallery. In the evening, after Janet had been to tea, we wrote about the Venetian pictures in the Gallery.

[170] *Friday Nov. 27. ’91. Pension Lejeune. Vienna
We went to the Gallery in the morning and saw the Dürers and the Holbeins first, and then went on to the Italians.
What a curious trait of intellectual dependence – or rather intellectual adrift-ness, one keeps coming across in English people! They seem so uneducated, so little alive, so clinging to the one intellectual straw they have got hold of, that when you upset their hobby, or take away their straw, they cry out, as if they are drowning. “O what shall I do? What can I catch hold of?” They often leave Oxford as helpless, intellectually, as children, if they are honest people. Of course a great many get so well “trained” there that the last intellectual word is said for them, and they become successful lawyers, [171] successful politicians, successful Bishops even. But the American boy’s tutor, who has come to this pension, is an honest boy, who has taken on none of the Oxford arrogance, and who has not been successfully trained to think himself as an Oxford man equal to anything. He has left Oxford positively, with the intellectual outfit of an infant. He looks upon all “great men” (Englishmen) as a little child looks upon its grown up relations. I remember well the battles I used to have with my little cousins, each one of us contending that my mother, and my way of being brought up was the best in the world. So he left Oxford thinking that Dr Fairbairn, the principal of Mansfield College, was the greatest man in the world, Robert Browning the one poet and Henry Jones (author of “The philosophical [172] system of Robert Browning”) his prophet, and metaphysics the only proper study of Man. He was just girding up his loins to read Kant, in order to get a “basis for religion” and an “explanation of the Moral Law.” (Well! well, do I know the “school” to which this painting belongs!!) I told him that Metaphysics was the last resort for ennui or for prejudice. He gasped, and turned wondering eyes upon me, and when, at some little length I explained my meaning, he said – oh how helplessly, how absurdly English!! - “Yes, you are right, but please tell me what I am to study.” Imagine Costa (who is just his age), or anybody who is alive, asking such a question! It frightened [173] me so, for he looked so limp and eager for advice, that I only said - “Whatever you would really enjoy. Metaphysics, if you think you would like it” - and fled.
[a newspaper clipping is pasted down, containing extracts from E. de Goncourt]
E. de Goncourt
[174] Saturday Nov. 28. 1891. Vienna
We went to the Albertina in the morning and finished our notes. Afterwards we wrote about the gallery, and went to Löwy’s. In the evening we wrote and read.

Sunday Nov. 29. 1891.
We went first to the Lichtenstein, but it was closed, so we went again to the Academy. At 12. 30 we went to the Richter concert, whose programme is below. The clavier-concert was perfect enchanting, like a picture of Watteau - just the same spirit. In the afternoon Herr Wichkoff and Mrs. Morison called, and we wrote in the evening. Two traits have developed themselves today chez les Americains. They went out this afternoon to visit the Cemetery, a thing Americans never miss!The other [175] national note is the way they treat their tutor. Having hired him, they use him tout à fait comme leur courrier. Tonight he had to leave his supper and take the maid to the train for Paris. And he is an Oxford man, far more of a gentleman in every way than anyone they are likely to know in America. They are true barbarians from the point of view of culture. He must be horrified a hundred times a day!

[176] Monday Nov. 30 ‘91 Vienna
Our last look at the Gallery - I am afraid we spent part of the day foolishly quarrelling!At 8-30 I started for London. The next day B. went to Venice, then to Bergamo, then to Milan.
x x x x x x x

Sunday. Dec. 13. 1891. 16 Viale Principe Amedeo Florence
We met again at 12. 40 at night.
Monday Dec. 14. ‘91 Florence
Unpacked. Called on Gertrude Burton, who is very ill. First glimpse of Uffizi and Pitti. Bliss. Catalogue in evening.
Tuesday Dec. 15. ’91. Florence
Santa Croce and shopping and a glimpse of the Pazzi Chapel in the morning. Met Costa in the afternoon. Gertrude’s children and mine met.

[177] * Wednesday. Dec. 16 1891. Florence
Uffizi in morning. Gertrude worse. Discussed metaphysics. Began Burckhardt, “La Civilisation en Italie au temps de la Renaissance”.

* Thursday. Dec. 17 ‘91 Florence
Studied the Venetians in the Pitti and Uffizi. Italian lessons. Catalogue.

Friday. Dec. 18. ‘91 Florence
Breakfast together. Went to the Ognissanti, Santa Maria Novella and S. Lorenzo. After lunch I wrote letters for Gertrude and then took tea with B. and Costa. B. had been at Alinari’s and calling on Miss Britten. In the evening we read Ruskin’s “Ariadne Fiorentina” - a book about engravings of Botticelli’s, chiefly done by tenth rate imitators of the people Ruskin detests most on earth – the Polaignoli!! [sic] He speaks of the Primavera and the Venus as tondos! and mixes up Mantegna and Castagno!
[178]
Saturday. Dec. 19. ‘91. 16 viale Principe Amedeo. Florence
Read Maurice Barrè’s “Sous l’oeil des Barbares”- a weakened - very much weakened Pater - an awful bore. Met Costa at the Uffizi and decided upon the chronology of the Titians in the two galleries. Had a bad headache, but went to Fiesole in the electric tram, walking down part way. Costa came to spend the evening, and we talked pictures.

* Sunday. Dec. 20. ‘91 Florence
Went in the morning to S. Marco and the Academy. In the afternoon I went to talk with Gertrude, while B. read Voigt. Read the Journal des Goncourts in the Echo de Paris - as lent by Costa.

Monday. December 21. 1891. Florence
Uffizi in the morning and notes on the Venetian pictures. Looked at the drawings. Costa came but did not stay long. Walked. Read Mill’s “Subjection [179] of Women” and enjoyed it keenly!

* Tuesday. December 22. 1891. Florence
Went to S. Spirito and the Carmini and walked out towards San Miniato in the morning -Called on Gertrude. Called on Costa’s aunt, Mlle Miranda, and enjoyed their cordiality surprisingly. I felt rather foolish in going, for I have nothing in common with her. Costa came back with me and paid a call. B. finished Voigt and began Ferrari. At 7 went to Arezzo

* Wednesday. Dec. 23. ’91 Albergo Victoria. Arezzo
Went to S. Maria del Pieve, the Duomo and the Pinacothek in the morning, and S. Francesco (Pier dei Franceschi frescoes) in the afternoon and a little walk to see the porch of S. Maria delle Grazie by Benedetto da Maiano. The architecture was just like Buonconsiglio’s, and wonderfully beautiful. The view of Arezzo through the arches was charming. This was a great pleasure, and it was a pleasure, too, [180] to see the charming little Monte di Pietà in the principal Piazza with its balcony at the top with a fence of vase ornaments. In the evening I read Layard and Guy de Maupassant’s Yvetteand other stories, and B. read Burckhardt upon Giotto and his followers. He found it excellent. Delicious night sleep.

* Thursday. Dec. 24. ’91. 16 Viale Pr. Amedeo Florence
We went again to the Duomo and several other Churches, especially to see Bartolomeo della Gatta. Took the train at 1 back. It was pretty cold in Arezzo, but we enjoyed ourselves. Called on Gertrude. Read Taine on Napoleon’s view of religion in the evening, and Crowe and Cavalcaselle on Masolino. Also “The Fountain of Youth” by Vernon Lee’s brother.

Friday. Dec. 25. 91 FlorenceChristmas
Worked steadily on our catalogue till 3 as it was raining. I called on Gertrude and B. on the Ways in the afternoon. [181]Read Crowe and Cavacaselle Masaccio in evening.
Saturday. Dec. 26. 9’1 Florence
Further notes on the Titians in the Uffizi. Began type-writing catalogue of Florence Galleries. B. asked the Ways to tea in the afternoon, and I felt absurdly excited at the idea of meeting her, for he had said so much about how fascinating she was and how much he liked her. Moreover, the fact that she had offered to become his “maitresse” interested me. She also felt intensely curious about me – and the result was funny to a degree. We each were left with the comfortable feeling of superiority, she feeling that I had no “charm” – absolutely none – and I feeling that she had little taste and no intellect. It was hard for me not to have “moral” prejudices against her – so hard, for she is the kind of woman - flirtatious and over-dressed and over-mannered - from whom [182] I have always fled - But when I am really just, I know that flirting is only one of the escapes from ennui, like religion, or devotion to children, and not so very much worse in its effect on the world. Still I don’t like it, and Mrs. Way shocked and shocked and shocked me, so that I was positively embarrassed and scarcely knew what to say. I liked Mr. Way exceedingly; still, on walking back with him, I found him heavy. Mrs. Way shocked me because she dragged all the conversation down to personal badinage, into which she did not even put the sparkle of wit. No doubt I shocked her by trying to talk à la Berenson, but unsuccessfully. B. was thoroughly tired after the ordeal, but he was amused to find that we were each [183] so calmly conscious of superiority. The truth is our “spheres”, though neither of them domestic, are so utterly different that we haven’t the slightest desire, either one of us, to shine in the other’s sphere. I am afraid she interests me no more. I believe it was stupid of me to say I would go to see her. Still I will do my best. What interested me most was to see that even a person like B. was not shocked with such arrant flirtatiousness, but on the contrary rather pleased with it. I suppose such a thing as instinctive “male vanity” does not exist in every man. Well, I can’t be jealous of her. I believe even if he should “fall in love” with her I could not now be really jealous.
We read “Candide”today and some of the new Revues Bleues,and B. read Crowe and Cavalcaselle on Giotto. Last night up till one o’clock we read Vasari’s Life of Titian.

[184] Sunday. Dec. 27. 1891. Florence
A hard rain. I went down to tell B. I would not go to the Bargello and found him asleep at 9. 30!We spent part of our day and all the evening re-casting our article on Savoldo. I read “The Wild Duck” (Ibsen) and B. his beloved Ferrari. I called on Gertrude, who says emphatically out of the fulness of her ignorance that B. is “altogether on the wrong track.” She doesn’t object to anything he does or says or thinks, but to his Soul – a thing about as tangible as the pre-Lockian “Substance”. Musgrave called on B. Read Burckhardt.

Monday. Dec. 28. 1891. Florence
Uffizi in the morning. Walked to San Miniato in the afternoon. Costa came to dinner and was nice. I had my first Italian lesson.

[185] Tuesday. Dec. 29. ‘91 Florence
Corsini Gallery in the morning. I called on Gertrude and Mrs. Way in the afternoon. She was so nice! Either she liked me, or she took me in. But at any rate I enjoyed her, and I understand the way other people enjoy her. She made me quite happy. We began to re-write our Titian article in the evening. B. had a cold. It depressed him, and he seemed to think we would be only fair weather friends. Ca, ce n’est pas vrai. Pour moi c’est pour tout de bon. He said yesterday that in arguing with a man you argued with him – with a woman, you argue with what somebody else has taught her to think.
Karin said that Winny had told her that if she wet on the floor, God would write it down in a book, and then the Devil would come and catch her and burn her up in his flames. How much simpler to say wetting the floor is not clean!
[186] Wednesday. Dec. 30. 1891. Florence
Got my permit at the Consul’s, while B. attended to his trunks. He called on the Ways and I on Gertrude - Worked on our Titian.

Thursday. Dec. 31. 1891. Florence
Breakfast together. Called for Mother at 9. 30. Morning shopping -B. with bad cold. Unpacked books and pictures. B. reading Ferrari.

Friday. January 1. 1892. Florence
Tree for children in morning. Emma taken ill. Walked with B. but unfortunately quarrelled – (both our faults!)But I went down to him in the evening and he came to me, and then came back and found me there.

Saturday January 2. 1892 Florence
Called for B. and went for doctor and nurse in the morning. Children very trying in afternoon. B. came in the evening [187] and we worked on our Titian -
Every girl ought to be made to spend six months taking care of little children before she marries. She would think twice before having children of her own!!The nurse came at 11!Children restless all night, and I horribly unhappy at being absent from B.
Sunday. Jan. 3. 1892. Florence
Walked with B. in afternoon. Lovely sunshine but we quarrelled horribly.
* Monday. Jan. 4. 1892.
Uffizi in morning - Made up our quarrel. Worked in evening.

Tuesday. Jan. 5. 1892.
Uffizi. Walk. Tea at B.’s. B. called at Ways.
*
 Wednesday. Jan. 6. 1892.
Uffizi. Work in evening.
Thursday. Jan. 7. 1892.
Uffizi. Went to Ways to dinner. B. very sleepy. Mrs. Way beautifully dressed and [188] milder in her flirtatiousness than before. She said she and her husband so thoroughly agreed with Mrs. Besant’s book on Population. I am sure if I had asked her which she recommended, the sponge or the syringe, she would have told me, sans gêne! Mr. Way said “It is better to be a pig than a prig”- and B., speaking of the English Aristocracy, said it made a great difference whether you belonged to the Peerage or the Beerage. He said the patron Madonna of England is Our Lady of Grundy!

Friday. January 8. ’92. Florence
Uffizi in morning. Called on Gertrude and found her worse. B. and I went to the doctor’s in evening. Loeser arrived.

[189] * Saturday. January 9. 1892. Florence
Uffizi. Saw Loeser. Rainy still. Tea with B. and Loeser. Unwell. Tired.

Sunday. Jan. 10. 1892.
Received Mr. Pennell’s article on the Vienna Gallery. Went to the Bargello and afterwards to B.’s rooms - where we semi-quarrelled because he would not answer Mr. Pennell. He was an angel, and promised to write every day. In the afternoon I helped Gertrude get off to the Home, and we took a little walk together, and then came back and answered Mr. Pennell’s article, and sent it off to the “Nation”.

Monday. Jan. 11. 1892. Florence
Uffizi in morning. Called on Gertrude. Tea with B. who went to see Costa, and then dined with Loeser, who was 28.
Tuesday. Jan. 12. ‘92. 
Uffizi - finished Venetians there. We called on Costa in the afternoon, and re-wrote our Paris Bordone article in the evening, and wrote to the Michael Fields.

[190] Wednesday. January 13. 1892. Florence
Pitti in the morning and finished re-writing our Paris Bordone. B. went to Costa’s and I took mother and Lady Albinia to the Uffizi - and then went to see Gertrude. Loeser came to dinner with us and we talked and looked at Lionardo drawings and talked - all of us rather bored, I fear.

* Thursday. Jan. 14. 1892 Florence
Pitti in the morning. Miss Farnell and Mr. Mitchell called in afternoon. B. called on Costa -In the evening we re-wrote our Paris Bordone, which I sent to the Michael Fields -
Friday. Jan. 15. ‘92 Florence
Pitti in the morning - still on the Venetians. Showed Miss Farnell, etc., some pictures which made B. cross. B. called on Costa. It was dreadfully raining, so I stayed at home and read Burckhardt. In [191] the evening we re-wrote our Bonifazio.
Saturday. Jan. 16. ‘92 Florence
Finished the Venetians in the Pitti. B. went to see Costa and I to see Gertrude. He did not come to dinner, and I read Vol. I of Yriarte’s César Borgia. B. invented the word “Pruritanic.” He went to hear Le Barbier de Seville with Loeser.

Sunday. Jan. 17.  92. Florence
Bargello in the morning -Tea with Loeser at 24 Lungarno Acciajuoli, Bernhard’s room, after the two had been to call on the Ways - a proceeding which they compared to a Turkish Bath. Bernhard said that Mrs. Way sighed delightfully. Loeser was rather nice. In the evening I read Layard and Crowe and Cavalcaselle on Lorenzo Monaco, and Prescott’s description of Charles VIII in Italy. Missed Bernhard.

[192] Monday. Jan. 18. 1892. Florence
* Santa Trinità in the morning to study the Lorenzo Monaco’s. Then I got a piano and a bonnet. In the afternoon it rained, but I took tea with B. after going to see the doctor about Gertrude. Read Maupassant’s “Monsieur Parent” volume.

Tuesday. Jan. 19. 1892 
Went to S. Jacomo Soprarno to look (in vain) for a Lorenzo Monaco. Then Costa came and we talked. B. lunched with him. I went to see Gertrude and told her she was too ill to get off to Switzerland, then came and took tea with Costa and Loeser at B’s. We tried to write our Bonifacio in the evening. I read Zeller.

Wednesday. Jan. 20. 1892.
Studied Lorenzo Monaco in the Uffizi and Academy and the Giotteschi  at Santa Croce [193] in the morning. Took mother and Lady Albinia to the Pitti in the afternoon - had tea with B. and Loeser, and called on Gertrude. In the evening we finished our Bonifacio. B. said most people want in pictures merely illustrations of their own sentiments.

Thursday. Jan. 21st . 1892. Florence
San Marco in the morning and Santa Maria Novella. We called on Loeser and walked up to Bellosguardo in the afternoon, and met Musgrave and went in to call upon him. Studied Italian and wrote to Gertrude’s husband and mother, telling them that the baccili of tubercular disease had been discovered in her sputa.

Friday. Jan. 22. ‘92
Took the children to school in the morning. In the afternoon we walked nearly to Maiano – home by S. Domenico. Spoiled my evening by a long talk with mother following upon the epistle from father:

[194] 14. I. 92.
My dear daughter,
Thine with reference to income is at hand. All this can be left until the spring, when I earnestly trust thee will return with thy children. Whatever I may wish to do for my children, I have nothing at command at present beyond what I have been appropriating for them, and this as thee knows has often been with extreme difficulty and inconvenience. It would be social ruin for thee and measureless suffering to thy family for thee to remain when thy children return, and I can contemplate no arrangement save of thy return. Families are dependent on their members reciprocally, and dependence (if it be nothing but pecuniary dependence) and independence do not go together. No claims of selfhood equal those made by parentage while children are young. [195] It is due to thee that I should lovingly and tenderly (sic!) as a father press these things upon thee.
More than all thee could hope to gain pecuniarily by self support would be lost by the expenses and inconveniences of a separated life. I earnestly advise thee to make the best of thy home. Thee made a false step by refusing the counsel of thy parents and it has turned out only less bad than we expected. And now at this crisis of thy life, yet more earnestly and with far more certainty as to the terrible results, we entreat thee not to desert thy children and family, and involve us all in social ruin. In thy conspicuous position, concealment of the facts of thy absence and the circumstances of thy travelling cannot be hoped for.
In much sorrow, but also much love
Thy Father
“I would simply say to her, use thy allowance decently and not against the primary instincts of nature. It is thine, but not to ruin us all by buying dynamite.” I cannot think it [196] would be right to give thee a rope with which to hang thyself - that is, to make it easy for thee to wander around Europe in this scandalous manner with a penniless Bohemian. No wise father could furnish funds for such a course to any child he loved.”
To mother: “If Mary deserts her children to wander around Europe with B. it shall not be on my money.”
Saturday. January 23. 1892. Florence
Met B. at S. Marco, and went home with him and had a long talk over our affairs.
Called on Gertrude with mother in the afternoon and took tea with B. He brought Loeser and Costa in the evening. As soon as Costa saw mother, he saw the whole situation, as regards the family. He is delightfully clever. He said he believed [197] that families who made a profession of the “emancipation of women” were in reality for more tyrannical and oppressive than families without highflown principles. Que c’est vrai!Read the second volume of César Borgia by Yriarte.
We are reading “À Rebours by Huysman – “Greek Literature” by Perryand even so many German books on Art.
Sunday. Jan. 24. ‘92 Florence
Fra Angelico in the Uffizi - and further talk over our affairs. Tea together.

Monday. Jan. 25. 92. Florence
Brancacci Chapel. Read Vasari’s Life of Fra Angelico. Called on Gertrude. B. went to call on Ways with Loeser.

Tuesday. Jan. 26. 92.
Read lives of Masolino and Masaccio in Vasari. Took a long walk behind Bellosguardo in the afternoon, and quarrelled but made it up before we had gone very far. B. dined with Loeser.

[198] Wednesday. Jan. 27. 1892. Florence.
I took the children to school and B. went with Loeser to the Pitti. In the afternoon I took mother and Lady Albinia to the Academy - then took tea with B., walked to San Miniato, and read Mrs. Jameson on Masaccio, Ghiberti, etc., and Crowe and Cavalcaselle. B. wrote an interesting criticism on À Rebours - by Huysmans. In the evening we dined with the Ways and Loeser at the Toscana. In some respects it was amusing, but Mrs. Way ends by being “assonante.” She can only talk in tête a tête, which is awkward in a party of five. Besides her interests are so very different from mine. She is Gertrude minus the moral sentimentality, an improvement, but then she is worse at least as far as I am concerned, because she is so frivolous; her amusements do not interest me. I should be content not to see her again.[199] Mother still here. It is a great bore.

Thursday. January 28. 1892. Florence.
Academy and Churches in the morning. Walked in the afternoon, called on Gertrude, who was horribly ill and nervous. Took tea with B. at Loeser’s.

Friday. Jan. 29. 1892 
Wrote to the Michael Field’s and copied B.’s criticism of Huysmans’ À Rebours.
Studied all the Filippo Lippi’s. Tea together and a walk.
Saturday. Jan. 30. 1892 
Went to Prato by the 10 o’clock steam tram. Saw the Gaddi’s, etc., in San Francesco, also the frescoes in the Duomo and the Gallery. Then went to the wonderful little Church by Giuliano di San Gallo, which was more overwhelmingly beautiful than ever. We had tea together and then a little walk. In the evening we dined at Loeser’s with [200] Mrs. Way, who was as bête as ever, even more so. This was such a dreadful aside for a dinner party of four –– !“Why do you like caviar?”B. Parce que ça me remous jusqu’au fond de mon estomac”- “Ah” a sigh and a very meaning look - “Comment est-ce-que vous sentez là?”…(silence) … “Dites - Moi! Comment est-ce-que vous sentez là - je voudriez tellement savoir!!”
It only left to be supposed that she wished the natural reply, “Voulez-vous essayer, Madame?”, which however was not forthcoming. Loeser, too, was impossible. He compared Lemaître’s “Mariage blanc” to Ibsen! – !

* Sunday. January 31. 1892. Florence.
Read Vasari’s life of Benozzo Gozzoli. B. went to see Loeser’s reputed Pontormos in the Uffizi. Evidently L. did not know the difference between Agnolo and Alessandro [201] Bronzino. I called on Gertrude, who was better.
Had tea with B. Felt cross, but he was so dear and sweet and entertaining that it was melted out of me.
Quant’è bello giovinezza
Che si fugge tuttavia
Chi vuol esser lieto, sia,
Di doman’ non c’è certezza."
Wrote to Edith in the evening and studied Italian.
Monday Feb. 1st. 1892. Florence
A glorious spring day!Took mother and the children to the cloister of Santa Maria Novella, and then B. and I went to S. Apollonia and S. Egidio to see Andrea del Castagna. [sic]After my Italian lesson we walked to Certosa. B. lunched with Loeser - who talked much about his former mistress, an actress in Germany. He said he could never love her ‘because owing to the birth of a child (not his) her vagina was too large for him. He said it would be a terrible tragedy all through her life – – – – !!B. called on Mrs. [202] Way in the evening who reproached him with ‘enjoying her with only two of his senses, sight and hearing.’ She said she could easily fall in love with him. To her all life is wasted that is not spent in sexual love, but she has been stupid enough to idealize it beyond the limits set by nature - to dream of it as something which is to satisfy her being entirely. Naturally her husband (who is charming) fails to meet the claims of this Ideal, and she seems frankly to be on the look-out for some one else. She thought she had found it in B. and she is rather puzzled that he does not respond, and can only explain it by thinking that his continual brain-work has ‘atrophied what makes him most really a Man.’ It is a pity she cannot fall in love with Loeser - they would make an admirable pair, or no, they would not, for he pretends to be intellectual, and she has no pretence to be anything but sensual, [203] except sentimental, perhaps. She thinks women ought to die at 45! I wonder if she will feel so when she attains that age. She will be simply awful at 35, unless she is too conventional and cowardly.

* Tuesday Feb. 2. 1892. Florence.
Saw the Alessio Baldovinettis in the morning (at the tomb of the Rucellai) and Santa Annunziata and the frescoes at San Minato, in the afternoon. The rain has come on again. Grandma told Karin today that it was not “genteel” to talk of the smell of things you were eating. Karin replied, with admirable impudence, “We talk about whatever we like to talk about.” Read several volumes of Maupassant’s short stories, and Burckhardt. B. read Perry’s Greek Literature.

* [Wednes]day Feb. 3. ‘92 
Saw the Alessio Baldovinetti at San Niccolò. Then at the Uffizi studied him and Domenico Veneziano and the Polaijuoli and Loeser’s famous false Pontormo’s.
Musgrave called on me. [204] We had a nice walk round by Gertrude’s - Gertrude did not enjoy “Sense and Sensibility”! She could “hardly wade through it,” and thought it dreadfully uninteresting compared to “Shirley”.
Mrs. Way enjoyed most the story of Maupassant’s called “Imprudence” in which, after making her husband describe his hundred odd mistresses, the wife begins to think that she might perhaps enjoy a variety of men.
I read “Sense and Sensibility” and Burckhardt.
Thursday Feb. 4. 1892. Florence
I took mother to Prato to see Giuliano di Sangallo’s Church, which she wanted to see, as being the most beautiful Church of the Renaissance. She was disappointed at first, but it grew upon her. It took her a long time to enjoy the frieze because garlands were the old-fashioned, stupid thing, when she was at the age of caring about pretty things - an age so [205] many people quickly outgrow! So she instinctively hates garlands, and feels as if they couldn’t be really artistic, because her grandmother used to arrange flowers in garlands. When I came back I had tea with B. and we took a walk. He and Musgrave came to dinner, and M. read us his really excellent translation of Dante - a great improvement upon the preceding translation. His elocutionary “way of reading” it almost spoiled it unfortunately, and he anticipated all our compliments by exclaiming himself - “What beautiful poetry!” “What subtle rhymes”- “What music in this line”, etc., etc. I was dishonest about my supposed “teetotalism”, partly from cowardice, but much more from the kindly desire to spare her pain, poor mother - whose universe is founded on the principle, “It is wicked to drink”- although she eats zabaiones!

[206] Friday Feb. 5. 1892. Florence
Mother tried to mix in a little religion in Ray’s matutinal fairy story - and said “so they prayed Jesus to make her good”-“O, don’t let’s play that”, said Ray promptly. “Well, couldn’t they pray for the fairy to come and make her good.” “No, don’t let’s play that. Let’s play she just came.”Sensible child! May she always be of the same mind!
We went to see many Ghirlandajos in the morning, and in the afternoon had tea at Loeser’s with Mr. Sumner and Miss Thayer of Boston. In the evening mother and I talked. Poor mother! Poor old people everywhere who try to make over young people’s lives according to their pattern - and poor young people! What an awful institution for hypocrisy and oppression the family is!
[in the left margin] There was an old man of Dundee who taught little owls to drink tea. For he said, ‘To eat mice is not proper nor nice!’ This punctilious man of Dundee!
Honesty is the one personal virtue, all one’s other virtues are questions of geography [207] and history. I shall never oppress my daughter!
Saturday. February 6. 1892.
I breathe freely at last, for mother is gone. She is so good and kind, but it is deadly to live with people who disapprove of you - and who are religious. Still, if she didn’t try to interfere with me, and do it effectively by worrying over me, for I hate to give her pain - I could enjoy her so much, even her stupidities, such as talking about women being a “later evolution than man”- and her belief in prayer. I took her to see the famous Giotto’s in S. Maria Novella before she started – Ruskin’s Giottos – which is about like saying servant girls’ diamonds. She thought it must be a crazy joke.
Then I went to B. - but I was so ill, being just taken unwell that I could do nothing. We spent the afternoon and evening together, and entered in the Venetians here, looked at photos of Ghirlandajo and read his article on ‘the function of science of art criticism’ -I began “Les Messieurs Golovleff” by Chtchédrine.
Yes, I must learn to be honest.
[208] Sunday Feb. 7. 1892. Florence
We met on the Academy and looked at the Pesellino and Botticellis. But I was feeling too ill to do much, so we came back. I read in the Galignani of a woman who domiciled herself in South Dakota in order to get a divorce, so I wrote to Emma Brayton for full information on the subject. In the afternoon we took a walk and quarrelled dreadfully. When B. begins to talk to me of my family and my relations to them, I behave like the cuttle fish which when it is attacked, squirts out an inky liquid and makes everything murky around it. (Or to be more accurate, like the skunk!) Then he gets angry and we say horrid things. We dined apart, I was so cross. But I employed the time well in writing home a personal “declaration of independence”. B. dined at Loeser’s with Sumner.

* Monday Feb. 8. 1892.
We love each other too much to stay quarrelled, and on the whole we are both, especially [209] B. too reasonable. So we had a nice talk in his rooms and then started to grapple with the Correggio article once more, as he has received a request to contribute something to a new magazine a friend of his in Boston is just starting, “The Knight Errant.”We worked at it in the afternoon, took a walk and continued at it in the evening. I think we are clever enough to learn to write fairly well - I hope so - and B. at least has plenty to say. So have I, if I dared to utter all the rage that is in me. B. said “The beginning of activity is the unconsciousness of ignorance”- Still reading Golovleff, B. reading “Le Prêtre Marié”.

Tuesday Feb. 9. 1892. Florence.
“The sum of the matter is that unless woman repudiates her womanliness, her duty to her husband, to her children, to society, to the law, and to everyone but herself, she cannot emancipate herself.”
But I try not to think about myself in general terms, lest, like most badly educated [210] “emancipated” people - so called - If all a victim to the latest fashion in Ideals! Probably I am in part that. Sometimes I have just the feeling which is complementary to what I have felt sleeping in the prairies under the open sky. Then I seemed to feel the great swirl of the revolving earth - bearing me along. And so in my ideas and conduct - at times, I realize that I am caught in the swirl, merely a tiny creature at the top, carried irresistibly on by the inevitable rush of ideas. My discontent, my rebellion, even my mistakes sometimes seem less individual than typical. But, curiously, I care all the more, for my sensations at least are my own, and I begin to know sweet from bitter and happiness from unhappiness. I never had such a consciousness of Life as I have now, when I realize how little any actions are “free-willed”.
Uffizi in the morning and further work on the [211] Correggio article. In the afternoon we had a beautiful walk from Fiesole by Poggio and Vincigliata back by Doccia. In the evening Loeser came to dine with me and I talked to him about giving Berenson money. Loeser said some very stupid and some very unkind things, and many which showed him utterly unappreciative - but yet I cannot say that I did not like him in the end better than in the beginning, although I fear the result of my talk is practically nothing. What I liked was that he did try hard to be honest, and that is nice. Besides it was impossible for me to keep agreeing with him that B. treats him in a very disagreeable way sometimes. I said I hoped I would never try to make my children lead my life, and he instantly exclaimed  “O it doesn’t matter about them, they are both girls! – – ! – – –!”
Who doesn’t at any rate unconsciously feel so?

[212] Wednesday Feb. 10. 1892 Florence
Met Costa and Gamba at the Uffizi. B. went to see Loeser and they ‘made it up’- It turned out that the real trouble was Loeser’s resentment at the cool letters I made B. write last summer when I so dreaded Loeser’s joining us - or talking to my family about what B. had written. Well, I hope it is all right now. I called on Gertrude in the afternoon, after a walk with Musgrave, who came just as I was starting out. Tea with B. and work on our Correggio in the evening. B. enthusiastic about writing a Life of Vasari.

Thursday Feb. 11. 1892
Went to S. Ambrogio and several churches in the morning to see Cosimo Rosellis, ending up with the Academy. Logan sent his story, “An Oxford Idyll” for criticism, but it was really too poor to be worth it. I was horribly disappointed. Called on Gertrude and took tea with B. Wrote the Correggio in the evening.
[213] * Friday Feb. 12. 1892.
Uffizi in the morning, studying the Credi and Verocchio. B. lunched here and we frivoled away the afternoon, enjoying it very much, till towards sunset, when we had a delightful walk. In the evening we worked upon the Correggio. I finished “Les Messieurs Golovleff” and began to re-read “Wuthering Heights.” B. read his Perry and Loti’s “Phantome d’Orient”.

Saturday Feb. 13. 1892.
Went to the Bargello in the morning to study the Verocchios, then to the Uffizi. I called on Gertrude in the afternoon and then took tea with B. Costa came in the evening and we compared notes on Naples, and looked at Lionardo and Botticelli photographs. Costa is so nice.

* Sunday Feb. 14. 1892. My’s 28th Birthday.
We worked on our Correggio in the morning, and walked to Mugnone in the afternoon. We had great fun making stepping stones across a brook.
Costa said last night that he had been [214] fool enough to let Loeser persuade him to go and lunch there to meet a certain Mrs. Way. Loeser told B. this morning that Costa had been so very anxious to make Mrs. Way’s acquaintance that he had to arrange a little luncheon for them.
Bernhard was very delightful all day. It is the happiest birthday I can remember.
I read “Agnes Grey,” and  Baudelaire’s “Poèmes en Prose”.
Monday Feb. 15. 1892. Florence
Pier di Cosimo at the Uffizi in the morning. Then we went to Gagliardi’s to see his Battle of Centaurs and Lapithae. Miss and Mr. Britten, Mr. Musgrave and Loeser came to tea at B.’s. I liked Miss Britten very much. We continued our grapple with Correggio in the evening. We discussed writing a “History of Taste in Italian Pictures.”B. spoke of Henry James’ “American” “ending in a marriage which did not take place”.

Tuesday Feb. 16. 1892.
Wrote Correggio morning, afternoon and evening. Took tea with Loeser.
Karin is really growing very pretty. I have found a good Kindergarten teacher. 
[215] Wednesday Feb. 17. 1892.
We looked at Filippino and Ghirlandaio in the Pitti and Uffizi in the morning. Costa joined in. He seemed dreadfully depressed. In the afternoon I went down to write quietly with B., as the four children and smoky fires made it quite uninhabitable here. But Loeser came in and had tea and interrupted us. We worked further on the Correggio in the evening, and I began to write children’s stories. If they are successful, I ought to be able to support myself by them.

* Thursday Feb. 18. 1892.
Fra Bartolommeo, Granacci, Ridolfo Ghirlandaio in the morning - also Raffaelo Botticini. We lunched with Loeser, who gave us a capital lunch. Musgrave came in the afternoon and while B. read Herrick,he dictated to me the first Canti of his translation of Dante, which I did for him on the type-writer. We looked at photographs, and B. almost decided that the so-called Signorelli fresco in the Sistine Chapel is by Fiorenzo di Lorenzo. Finished our Correggio and sent it off to Cram. I wrote more of my story.

[216] Friday Feb. 19. 1892. Florence
Looked at Fra Bartolommeo drawings in the Uffizi and at the Andrea del Sarto’s. B. had a letter from Ned Warren saying that he could only give him one hundred pounds more, in the middle of May. It was a very nice letter, although it conveyed bad news. Still it is something to have that £100. Afterwards we came home and talked over our plans very seriously. B. decided not to leave Italy this summer. In the afternoon he went to see Mme Villari, and I went to see Gertrude. Then we looked at photographs  Michelangelo, the Ferrarese, and the later Florentines. We were both sleepy in the evening, so we did not do much except discuss our plans, which are indeed somewhat hard to arrange!I am reading an Italian translation of Tourghenieff’s “Assia”with my teacher, Mme Zucchelli.

x Saturday Feb. 20. 1892.
I went to B.’s and darned some of his stockings. Then we went to Alinari’s and looked over photographs. Costa joined us. He wanted me to come and meet the Countess [217] Gamba, but I invented an excuse. She is a great gossip, and I don’t want to meet her. She is said besides to be noted for “Lesbianism” - qui ne me plait pas du tout - Still of course that is not my affair. B. told me that Musgrave is a great haunter of brothels. He said one day to B. and Loeser that whenever he felt he did not want a woman, he knew he was ill, and that when he wanted one, he usually had one. Wouldn’t mother’s and Alys’ hair stand on end if they knew he was that kind of a man, and they had so much enjoyed his society and had described him as “a perfect gentleman”! What I hate more about him is that he judges all women by the women he meets in brothels. He said once that the thoughts of all women were centered about the small part of their body occupied by their sexual organs. It was months after I heard that before I could bear the thought of him. Mais, enfin, qu’est que ça me fait? He has translated Dante very well, and you can’t expect too much of one person - but I LOATHE him, and I wish he’d get syphilis and die in tortures! B. dined with Loeser and I called on Gertrude and wrote my Cedars Book. [218]

Sunday Feb. 21. 1892. Florence
A year ago B. arrived in London. We have had much trouble, but far, far more happiness since. We have been separated very little. In the morning we went through the Academy with Costa, and then came back and looked at photographs. The children went to Certosa, and we walked to San Miniato. In the evening we went over our Hampton Court catalogue and the article on Titian. My Italian takes so much time. I have no chance to read. B. had a bad headache in the evening. Ray came back disappointed from Certosa “because there were no monkeys”- She thought when I said “a monk would take her round”, I meant a monkey.

Monday, Fed. 22. 1892.
A rather disappointing day - partly on account of the severe depression which always comes on when one is getting a bad cold. We went over some of the photographs in the morning, and then went to the Pitti. Costa and Loeser were there. Costa called B. ‘assonant’ over an Andrea del Sarto he did not know, and Loeser smiled with most malevolent glee at it. This [219] made B. so angry that he went away in a rage. I went with the others to the Martelli collection and saw a young Velasquez (according to Richter), the head of a man with a grey beard and red cap, and 2 Beccafumis, Luper [cali] feasts. Besides this, a Donatello heraldic beast in gold on the stair-case, a St. John and the head of a little St. John, and a David which shows clearly where Michelangelo got his inspiration.
After lunch I went with the children to a Washington’s Birthday party which Gertrude gave, a very pretty, dainty little affair, which made a deep impression upon the children. Then I wrote my Cedars story till B. came. The evening was sacrificed to a discussion of the quarrel of the morning. B. found me very unsympathetic and insensitive. So I was, I think. My brain felt quite numb. I hope he will not often get so angry with people. Whether they deserve it or not, it doesn’t pay. He determined to drop Loeser, and in that I think he is wise, for Loeser is a simply awful bore. But it would be a mistake to quarrel open with him. Well - it was all rather a bore, yes, a decided bore.

[220] * Tuesday Feb. 23. 1892. Florence
Went to B.’s and looked over photos, and read Vasari on Correggio. In the afternoon I took Mr. Graham Bell to Gertrude’s, and then came back, and all the rest of the time till 10. 30 we spent over an interesting and very, very suggestive piece of criticism of B.’s: the “inner law” of literature, the fact that it tends always to be a contemporary description of the struggle of the individual to assert himself against the forces that tend to hold him down.

* Wednesday Feb. 24. 1892.
Washed my hair so did not meet B. at the Uffizi till 11. 30. Looked at Andreas there and at the Pitti. Walked in the afternoon, and saw the Perugino and the Franciabigio in the Calza, near the Porta Romana. I enjoyed the Perugino very much. I read a series of conférences by Mme Marie Deraismes called “Éve dans l’Humanité.” It is not very good, though there are some good things in it. B. was to have dined with his friend Jenkins, but J. did not come.

[221] Thursday Feb. 25. 1892. 
Saw the Andrea del Sarto frescoes at the Annunziata, the Scalzo, San Salvi and the Academy. I paid a short call on Gertrude. After my Italian lesson I went to B.’s where I had tea and read Huysmans’ wonderful little story called “Un Dilemme”. We walked and in the evening I read my children’s story to B. I have decided to call it Linden Stories or Summers at Linden. He was very enthusiastic, to my great delight. How I hope it may turn out to be worth while. I would like to support myself.

* Friday Feb. 26. 1892.
I went to the tomb of the Medici in the morning. Gertrude gave me her criticisms on our Correggio article, which she seemed to think very important, but I did not find them worth much. After my lesson we walked nearly to the Villa Careggi. Then came home and had tea. B. read Creighton’s History of the Papacy and I finished the first part of my Linden Stories. B. thought it good. After he went, I read some of Creighton too.

* [222] Saturday Feb. 27. 1892 Florence
Looked at Pontormo and Bronzino in the Pitti and Uffizi. Coming home I met Edith Kendall who asked me to dine. I took tea with B. and then went on. On the whole, I was bored. I was never very much Edith’s friend, and now I feel as if we had very little in common. She is travelling with an awful brother. She looks very fat and middle-aged, with yellow wrinkles about her eyes. I wonder if I look as old and commonplace to her?! No doubt. Well, I’m not, I know. I went back to B.’s at 9 and found he had had a call from Musgrave. Read Maupassant’s “Clair de lune.” There is no doubt that Huysmans’ simple story “Un Dilemme” makes Maupassant’s seems very “prepared”, almost melodramatic.
Sunday. Feb. 28. 92
Galleries closed. Went to see Rossi at San Lorenzo. Met Costa on our way back and he came to fix my type-writer, which had gone wrong. He stayed all the morning. It wasted some time - but on the whole we were glad to see that he was in no way angry -In [223] the afternoon we walked and semi-quarrelled about walking (which I hate), but made up. Then I took a nap while B. read Creighton’s “History of the Papacy,” and then I type-wrote half of my story. Alas! that time is so short. I had a hundred other things I wanted to do in the day - but I went to bed at 11 very tired.

Monday Feb. 29. 1892.
(Where will we be on the next 29th of February? Together, at any rate.) Met at S. Lorenzo and looked at Rosso and Bronzino and Sogliani, and the Donatello altars. The Library was closed. Costa came late, but we met him on our way out and we went to the Gallery connected with Santa Maria Nuova. The Hugo van du Goes impressed me very much. Then we went to the Academy to look for a Lorenzo Monaco mentioned by Crowe and Cavalcaselle - Milanese. Then I came home and had my lesson and went to see Gertrude. She says she only reads when she really has nothing else to enjoy. That would be entirely praiseworthy if she did not at the same time pose as a “cultured” person and venture upon literary criticisms. B. came to tea and read Creighton while I finished type-writing my story.

[224] * Tuesday March 1. 1892. Hotel Globa e Londra Pistoia
We studied Verocchio, Lorenzo di Credi and Ridolfo Ghirlandaio in the Uffizi in the morning. In the afternoon we went to Pistoia. I read Creighton on the way, and B. read Symonds’ “Essays, Speculative and Suggestive.”After a vermouth we walked about and looked at the town. We had a delicious evening before a fire - I reading Creighton and B. Huysmans’ “En rade,”a sort of more realistic, because less romantic and epic “La Terre”-It was delightful -!

* Wednesday March 2. 92 Florence
We “did” Pistoia, studying especially the Lorenzo di Credi in the Duomo. How fascinating it is to feel that you really possess a fresh town!In the evening we arranged our photographs in the new covers. We were tired.

Thursday March 3. ‘92 
We met in the Strozzi Chapel. B. was lazy, so we went to Alinari’s and then to his rooms, where I wrote to Edith and he arranged photographs. Emma went out in the afternoon so I took care of Karin. B. came to tea, we had a small stroll, and then continued our photograph work. In the evening I read Creighton and he [225] read Crowe and Cavalcaselle and Morelli. Still tired.

Friday. March 4. 1892. Florence
Uffizi - drawings and Bronzino. I stole off and enjoyed myself among the Venetians for a while!We finished arranging photographs here in the afternoon and took a little walk. I went to see Gertrude. Read Creighton. B. read Huysmans’ “En ménage”and Eastlake’s Literature of the Fine Arts.”

Saturday March 5. ‘92
I was unwell and felt very ill. Went to B.’s and helped arrange his photographs.
Began our Lotto article. He went to Castello to see the Ridolfo Ghirlandaio’s and I went to see Gertrude. Her Swiss maid Julia used to be a waitress at a hotel. She said there was not a man who came who did not try to seduce her. She disliked gentlemen least, because they were polite and understood No. She utterly refused to hear of such a thing as a chaste man! O it is so easy to forgive where there is love, so it does not need forgiveness, but the very beauty of that somehow makes the other so disgusting. How it turns my heart to bitterness and I know what I am writing of. But worse still, to try to seduce a girl because she has to work for her living and belongs to a lower class - Ugh! It is horrid. It is uncivilized.

[226] * Sunday March 6. ‘92 Florence
We took our Perugino photographs and went to see all the Perugino’s here, including the Cenacolo attributed to Raphael, which Morelli attributed to Manni. It is clearly, clearly a Perugino, however. I took Gertrude a selection of photographs in the afternoon. She seemed worse. In the evening I had a terrible headache. B. was so sweet and nice; he sat by the fire and chatted gently, till he drove my head-ache almost away. We sent the Michael Fields his essay on the ‘struggle of the individual’ in literature.

Monday. March 7. 1892.
We went to the Uffizi in the morning. It was bitterly cold. In the afternoon we grappled with something about Art which B. wrote last night. It is one of our special anniversaries today. A year ago we were at Haslemere. Florence Ayling was there too. What a dreadful year - yet how happy I have been. One could not pay too dear for such joy.
Emma said today, when Karin took a long nap and did not get her dinner till 4, [227] that she looked at her and thought: “Dining at quality hours!” 
What an expression!! O Life! That such things should rise naturally to anyone’s lips!
B. said that the cult of the Magdalen came in with the Jesuits, a very fruitful subject for thought.
* Tuesday March 8. 1892.
Pitti in the morning. Took tea with B. We had dinner together at La Toscana. We had to compose an elaborate lie for Loeser’s benefit, but it was rather amusing.
Wednesday March 9. ‘92
Received news of B. F. C. C.’s election to the County Council. Worked on photographs all the morning. Karin’s birthday party in the afternoon -B. called on Costa. Loeser came to dinner. He was a solid bore. B. finished “En Ménage” and I began it and read it half through.

Thursday March 10. ‘92 (Karin 8 years old)
As it was raining, we spent the morning over photographs. After lunch we went to a concert. [228] Costa and Giovanni were there. Half way through Costa said, “I am boring myself to death,” and went out. We followed his example very shortly. We discussed the heinousness of various offences rather hotly. I must say that going about with prostitutes seems to me about the worst and hatefullest personal vice a man can have, but B. does not agree with me! Some things make me boil over with indignation. Mother wrote in a letter to Alys, which Alys sent me, that if Alys wanted to go to a certain party, she would send Jessie or Lucy to bring her home in a cab -! Alys is a great strapping young woman of 24, bigger than either of the servants, and fully as well able to take care of herself. Moreover, servants are far more likely to be accosted than ladies. But they are poor, so it doesn’t matter. I know society is organized so - but I hate to realize that mother gives it her approval. She would not have before she came to England. Then the utter indignity for a girl like Alys, who calls herself “free,” of being sent for - I would rather be Lucy or Jessie than a helpless [229] creature of 24 who can’t go about London alone. - But such thoughts are too sickening. I went to see Gertrude. B. began Vol. II of Creighton’s History of the Papacy.

* Friday March 11. 1892. Florence
Uffizi – Shopping -B. lunched here. Edith Carpenter’s cousin, Miss Mary Foote, called here. She talked thoroughly New Englandy gossip about Edith’s moral qualities and described Bond as “so just”- It amused me immensely. She thought every man ought to go into business. We had a rather lazy evening, with music, etc. I am reading Hawthorne’s “Wonder Book”to Ray. I wrote more of my story. B. read the Revue de Deux Mondes upon the recent Rembrandt books.

Saturday March 12. 1892. 
San Spirito, several other Churches and the Uffizi in the morning. In the afternoon we walked out to a convent school, La Quiete, near Castello to see some Ridolfo Ghirlandaios. It was a beautiful afternoon. In the evening I wrote my story and read En ménage. B. continued with Creighton. Began Tanglewood Taleswith Ray.

[230] Sunday. March 13. 1892. Florence
Pitti in the morning, and further arrangement of B.’s photographs. After lunch B. called on Gertrude while I wrote my story - Then I took Ray to call upon the Footes, while B. went to call upon a disconsolate honeymoon couple named Adams, who have been married a fortnight and are nearly bored to death*.[marginal note: ‘They separated for good a few months later.’ Why will Americans always talk about oysters and sweet potatoes and things to eat in general? My Americans appeared to travel from table d’hôte to table d’hôte, chiefly for the purpose of proving that no place is so comfortable as America – Well - they are welcome to go back and welter in it!Then I went to see Gertrude for a little while. In the evening we wrote our Lotto.

* Monday March 14. 1892. The King’s Birthday. 
Being a popular holiday, with the Galleries closed, of course it poured. We arranged photos, all the morning. Loeser came in. In the afternoon we had a walk. Were too tired in the evening to do much, so I read and finished “My Trivial Life and Misfortune,”and B. went on with Creighton. He is reading Huysmans’ La Bas. It is strange how little most “serious” people think about l’art de vivre. Truly it is a most difficult art - how rare are [231] the successes. Yet when we grow old, we won’t look back upon our famous books, on the flattery we have had, but to our early loves, to our real enjoyments, perhaps after those in which the intellect has had little part. I shall never forget the charm of these days, not only for the awakening of my intellect, delightful as it is to begin to think freely, but because Bernhard looked in such and such a way, and spoke in sweet, deep tones, and because Ray came every evening and laid her selfish little head against my knees, while I read the Wonder Book to her. Ah! How happy, happy I am. Truly this is a marvellous year. There is only one cloud, and that is that in spite of our promises, we never seem to work upon our Hampton Court Guide. We planned to do so much this winter, and Bernhard has often promised he would have it ready for me to take back to London when I go - but I doubt it - Alas! it will make everything much, much harder for me. Still I could bear that well enough it I were really convinced that it is not worth spending time over, but I am not convinced of that.

[232] Tuesday March 15. 1892. Florence
We went to the Palazzo Vecchio this morning and had a look all round. The Salviatis and Vasaris were awful. But to make up for all, we came at the end upon a wonderful little chapel, the private chapel of Eleanora of Toledo, decorated with marvellous frescoes by Bronzino. One of them, the drowning Pharaoh’s army in the Red Sea, had as wonderful a stretch of sunset coloured water as even Besnard could have painted! It reminded us both of Besnard. The figures, too were drawn with his delicious precision, that gives one such a sense of completeness. There is no hesitation, nothing tentative about him. What he undertakes to do, he carries through perfectly…Then we went to the Badia, and then to the Uffizi, where we met Costa, with whom we walked back. I had an Italian lesson. Then the little Foote boy, and Arnold and Harold and Yvonne came, so that there was a merry party of children. Then I went to B.’s where we had tea with Mr. and Mrs. Adams and Mr. Jenkins. Deadly!In the evening I wrote my story and B. read Creighton. [233] It would be hard for me to put into words the unhappiness that comes over me sometimes when I see that, even where he has solemnly promised to do it, and where there is every motive to lead him to work, Bernhard will not take the trouble. We often quarrel over it. If I could make up my mind to it, it would be easier. But he promises me each time that he will do it, and is hurt and discouraged when I cannot believe him. I can’t do the work. I would so gladly. Of course when I see him like this in regard to the Hampton Court Guide, I cannot help foreseeing that it will be equally easy for him all along to find excuses for not doing any work of the kind. It is so easy to think that it will be hard to get things published, or that nobody wants them, about anything he is likely to write. I see that the same thing will happen to the Vasari he sometimes talks of writing next summer. He is unwilling to do work that is disagreeable, and writing is disagreeable to him. I think he is wrong, and it makes me unhappy. I cannot blame myself for having set my heart on doing the Hampton Court Guide, for at one time he was as enthusiastic as I over it, and he has promised me, so many times, to do it this winter. What have we done? We have [234] perhaps out of all the winter spent a dozen hours over it, re-writing the Savoldo, the Paris Bordone, and the Bonifazio, and going over the Titian. I believe that not once have we begun it without decided protest on his part, and his trying to make me feel that it was stupid of me to urge it just then, when he would be so much better occupied with something else. It is unkind of him, for he ought to know how much I care, by this time. But it is not only the personal feeling shown about it, as the knowledge that his failure, if he does fail in this, is what I must expect in him all through our lives. It reminds me, in some ways so horribly, of promises B. F. C. C. kept making me - especially after I had got cross and discouraged over it - really to give up a little time to writing what I hoped for, a ‘primer’ of philosophy. I do not mean the things are at all the same, but they treated it in the same way. If B. would say at once, ‘I won’t do it, I don’t consider it worth wasting my time on’, I would have to give it up. Of course I would be awfully sorry, but it would give me more [235] hope for the future than his present way of dealing with it, which is to acknowledge that it ought to be done, to promise to do it, and then to put every obstacle in the way when any chance comes - Yet he expects me to believe that he has the capacity for work of this kind - ! He often talks about the books he means to write, but more and more, as I have to judge him by what he does now in regard to the thing in hand, my heart sinks when he talks of these books. It is not that writing is the one occupation worthwhile. But it is worthwhile not to let momentary laziness and weakness interfere with what you have made up your mind it is best to do - It is so easy to find excuses - a much less clever person than B. could find a hundred reasons why the Hampton Court Guide isn’t worth writing. It would be more than easy for me to find reasons for not writing my child’s story. Indeed, it is hard to find reasons for going on! But I notice he does not encourage me to yield to pleasanter things and put the story by. The excuse is that my story may probably bring in immediate money, whereas all writing is, at any rate at first, unremunerative. He often speaks as if he thought he might make money by it in the end, but you don’t reach [236] the end without beginning - Now, we are assured of a certain amount of money, at least we will probably have it, so that I could easily say - “O, why should I bother myself with these stupid children’s stories”- But I want us to be independent. It is horrible to me to take money from Frank. No doubt it is a kind of pride, but I want everyone who knows us to feel that we are able to be independent. And if we are, if one of my books succeeded, I should be sorry to have it all my work. B. had a little while ago a feeling as if he would like to show everyone that he is worth something. Well, I would like it too, and very much. I would not like it, if I thought it would be really bad for him. But alas! I feel that it would be good for him, and that it is the nicest thing for him to do, now that he no longer goes among people to give them his ideas - and especially when he makes a point of not giving them. I feel stupid, as if I could not exactly reach the bottom of the feeling I have about this. But I have a strong [237] feeling about it, which makes me at times very unhappy. He cannot blame me for having had hopes that he would stick to this. He is failing to justify my hopes, without convincing me that I am wrong. That is miserable - it is sometimes in my mind when I am happiest - the feeling that our position is so insecure and that he will not help me to make it more secure. Of course it would be thousand times easier for me to demand money to carry out all my schemes with him, if I could point to a finished work which was the result of our being together. But if all I have to show for my winter with him is a child’s story, which I could have written as well at home. I know father, and mother, too, will put more difficulties in my way, than they would if I said, “We have done this”, “we are going to continue working. We need to be together for our work.” People always go by what you can show, not by what you are in yourself. Besides, they know too little to appreciate what I may have learned - B. knows all this as well as I, and he won’t help me, simply because it involves sacrifice of time on his part. I am quite sick of asking him to do it. Sometimes I think I will throw it all into the fire. But I hate not to leave the chance open to him - [238] small as it is now, when more than three months have slipped away.
I wonder if all these thoughts make me love him less. Certainly they make me feel as if I could not count upon him to help me practically. Now, particularly in such a situation as ours, somebody must be a little practical, of course the less we are associated in drudgery, the more will it fall upon me alone to do, particularly if my family get any inkling of the fact that I am writing my child’s stories in order to have money to give to him, while he sharpens for his pleasure (and for mine) his eye and his intellect.
Still, the practical side is not all It is the queer feeling you have for a grown up person who promises to do a thing, and then lets every obstacle come in his way, without facing it and saying clearly I was a fool to undertake it. I know he would be disappointed if I let my stories fall through - saying at the same time ‘O, I mean to write them.’ ‘I ought to do it.’ He would be disappointed practically as I am, because of the advantage we hoped for from them, and [239] naturally he would feel somewhat more alone, cast on his own resources, without anyone willing to do much to help him. And he would be too clever to hope much from any similar undertaking of mine, altho’ of course a lucky chance might make me hit on something pleasant all the way through. But he would not help drawing inferences as to my future - particularly if I talked much about the writing I was going to do.
I am going to show him this. I think it is clearer than I could say it, although not very clear! But I am apt to lose my temper if I try to say things, or else I cannot think of everything at once, and what I say sounds silly.
I do not like to give up altogether the idea of our making use of what we know in writing - neither do I like to think of myself as being the member of the firm to have all the bother of writing.
A Year later
All the same he was right about the Hampton Court Guide being a perfectly unpublishable affair!! But I cannot complain now of his being lazy in writing - the dear!
[240] Wednesday March 16. ‘92 Florence
Met at the Annunziata - looked at all the pictures in the church, ditto San Marco. Then the Innocenti - Then we found the fresco by Raffaelino di Carli said to be at St. Maddalena dei Pazzi - but in a school-room near by. Then we went through the Museum of Antiquities. All this time we were rather quarrel-y. B. came to tea. In the evening we talked over what I had written. He was very nice. He promised to do the Hampton Court Guide for me. He said my feeling so, was about as silly as if he should fall into utter discouragement because I failed to get up much interest in the Florentines. The parallel was too good for me to deny.

Thursday March 17. 1892.
Met at S. Maria Novella, looked at the Bugiardini. Then went to the Corsini Gallery and then to the Uffizi. I called on Gertrude. B. lunched with Jenkins, who offered him his rooms for next winter. We walked in the Boboli Gardens, and then I went to call on the Footes. After dinner we worked on our Lotto. Gertrude is going to send Miss Bliss away.

"""




rough_word_count_orginal = len(markup_text.split(' '))

# we are running it through the dangg machine
client = OpenAI(
    base_url="https://api.studio.nebius.ai/v1/",
    api_key=os.environ.get("NEBIUS_API")
)   


completion = client.chat.completions.create(
    # model="meta-llama/Llama-3.3-70B-Instruct",
    # model="nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",
    model="Qwen/Qwen3-235B-A22B-Instruct-2507",
    messages=[   
        {
            "role": "user",
            "content": markup_text
        }
    ],

    temperature=0,
    max_tokens=0,
    stream=True
)

response_text = ""
chunk_count = 0
for chunk in completion:
    content = chunk.choices[0].delta.content
    response_text=response_text+content
    chunk_count=chunk_count+1
    if chunk_count>175:
        job_data['text_markup'] = response_text
        rough_word_count_markup = len(response_text.split(' '))
        job_data['status_percent'] = f"{rough_word_count_markup}/{rough_word_count_orginal} ({int(rough_word_count_markup/rough_word_count_orginal*100)}%)"
        json.dump(job_data,open('test.json','w'),indent=2)
        chunk_count=0



job_data['text_markup'] = response_text
job_data['status_percent'] = f"{rough_word_count_markup}/{rough_word_count_orginal} ({int(rough_word_count_markup/rough_word_count_orginal*100)}%)"
json.dump(job_data,open('test.json','w'),indent=2)




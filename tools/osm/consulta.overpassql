[out:json][timeout:180][bbox:-23.86,-53.43,-23.68,-53.21];
(
  way["highway"]["name"];
  nwr["amenity"~"^(hospital|clinic|doctors|pharmacy|police|fire_station|fuel|school|university|college|bank|townhall|bus_station|marketplace|post_office|place_of_worship|restaurant|fast_food)$"];
  nwr["shop"~"^(supermarket|convenience|mall|bakery|butcher|greengrocer|department_store)$"];
  nwr["healthcare"];
);
out geom;

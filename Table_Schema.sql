drop table if exists NCS_Trends_Data ;
create table NCS_Trends_Data (
  id integer primary key autoincrement,
  SwithcID text,
  Date_n_Time text,
  Status text
);
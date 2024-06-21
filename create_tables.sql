-- Active: 1712569874159@@127.0.0.1@3306@dormitory
create table Account (
  UID int primary key,
  username varchar(50) not null,
  user_password varchar(50) not null,
  -- 账户类型，0 表示学生账户，1 表示管理员账户，-1 表示超级用户
  account_type int default(0) not null,
  unique (username)
);

create table Building (
  BID varchar(10) primary key,
  gender enum('男', '女') not null,
  capacity int,
  occupancy int
);

create table Room (
  BID varchar(10),
  RID varchar(10),
  capacity int not null,
  occupancy int not null,
  primary key (BID, RID)
);

create table Student (
  SID varchar(15) primary key,
  name varchar(15) not null,
  department varchar(30),
  phone varchar(15),
  email varchar(15),
  gender enum('男', '女') not null,
  UID int,
  BID varchar(10),
  RID varchar(10),
  avatar_path varchar(255),
  foreign key (UID) references Account(UID),
  foreign key (BID, RID) references Room(BID, RID)
);


create table Administrator (
  GID varchar(15) primary key,
  name varchar(15) not null,
  phone varchar(15),
  email varchar(30),
  UID int,
  avatar_path varchar(255),
  foreign key (UID) references Account(UID)
);
-- drop table Administrator;

create table Maintenance (
  MID int primary key auto_increment,
  BID varchar(10) not null,
  RID varchar(10) not null,
  SID varchar(15) not null,
  application_date date,    -- 申请日期
  updated_date date,        -- 记录更新日期
  progress int not NULL,    -- 进度，0 表示已提交，1 表示正在处理，2 表示已经处理结束，-1 表示已驳回，-2 表示异常
  foreign key (SID) references Student(SID) on update cascade,
  foreign key (BID, RID) references ROOM(BID, RID)
);

-- drop table Maintenance;

create table Visitor (
  VID int primary key auto_increment,
  name varchar(15) not null,
  phone varchar(15) not null,
  BID varchar(10),
  arrive_time date,
  leave_time date,
  foreign key (BID) references Building(BID)
);

create table Manage (
  MID int primary key auto_increment,
  GID varchar(15),
  BID varchar(10),
  foreign key (GID) references Administrator(GID) on update cascade,
  foreign key (BID) references Building(BID)
);

create table Counter (
  name varchar(15) primary key,
  val int
);

insert into Counter
  values ("uid_count", 0);

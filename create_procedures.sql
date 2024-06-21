

create procedure create_room(
  in BID varchar(10),
  in RID varchar(10),
  in i_capacity int
)
begin
  -- 声明一个异常处理器
  declare exit handler for sqlexception
  begin
    -- 回滚事务
    rollback;
  end;

  -- 开始一个新事务
  start transaction;
    -- 插入新房间数据
    insert into Room (BID, RID, capacity, occupancy)
      values (BID, RID, i_capacity, 0);
    -- 更新建筑物的容量
    update Building set capacity = capacity + i_capacity
      where Building.BID = BID;
  -- 提交事务
  commit;
end;

create procedure checkin_student(
  in p_SID varchar(15),
  in p_BID varchar(10),
  in p_RID varchar(10)
)
begin
    declare gender1 varchar(5);
    declare gender2 varchar(5);

  -- 开始一个新事务
  start transaction;

    select gender into gender1 from Student where SID = p_SID;
    select gender into gender2 from Building where BID = p_BID;
    
    -- 检查学生 ID 是否存在
    if not exists (select 1 from Student where SID = p_SID) then
      signal sqlstate '45000'
        set message_text = '学生 ID 不存在，无法入住';
    end if;

    -- 检查学生是否已经入住
    if exists (select 1 from Student where SID = p_SID and (BID is not null or RID is not null)) then
      signal sqlstate '45000'
        set message_text = '学生已经入住，无法再次入住';
    end if;

    if gender1 != gender2 then
      signal sqlstate '45000'
        set message_text = '学生性别不符合公寓要求，无法入住';
    end if;

    -- 检查房间是否还有空位
    select occupancy, capacity into @current_occupancy, @room_capacity
      from Room
      where BID = p_BID and RID = p_RID;

    if @current_occupancy < @room_capacity then
      -- 更新 Room 表的 occupancy
      update Room
        set occupancy = occupancy + 1
        where BID = p_BID and RID = p_RID;

      -- 更新 Building 表的 occupancy
      -- update Building
      --   set occupancy = occupancy + 1
      --   where BID = p_BID;

      -- 更新 Student 表的住宿信息
      update Student
        set BID = p_BID, RID = p_RID
        where SID = p_SID;
    else
      -- 如果房间已满，则抛出错误
      signal sqlstate '45000'
        set message_text = '房间不存在或者房间已满，无法入住';
    end if;

  -- 提交事务
  commit;
end;

drop procedure checkin_student;

create procedure checkout_student(
  in p_SID varchar(15)
)
begin
  -- 开始一个新事务
  start transaction;

    -- 检查学生是否已经入住
    if exists (select 1 from Student where SID = p_SID and (BID is not null or RID is not null)) then
      -- 更新 Room 表的 occupancy
      update Room
        set occupancy = occupancy - 1
        where BID = (select BID from Student where SID = p_SID) and RID = (select RID from Student where SID = p_SID);

      -- 更新 Building 表的 occupancy
      -- update Building
      --   set occupancy = occupancy - 1
      --   where BID = (select BID from Student where SID = p_SID);

      -- 更新 Student 表的住宿信息
      update Student
        set BID = null, RID = null
        where SID = p_SID;
    else
      -- 如果学生没有入住，则抛出错误
      signal sqlstate '45000'
        set message_text = '学生尚未入住，无法退房';
    end if;

  -- 提交事务
  commit;
end;

select * from student;

call checkout_student('0011');

drop procedure checkin_student;

insert into Building (BID, gender, capacity, occupancy)
  values ('B001', '女', 0, 0);
insert into Building (BID, gender, capacity, occupancy)
  values ('B002', '女', 0, 0);
insert into Building (BID, gender, capacity, occupancy)
  values ('B003', '男', 0, 0);

select * from manage;
select * from building;

insert into Manage (GID, BID)
  values ('G003', 'B002')

select * from student;

select * from room;

call create_room('B001', 'R001', 4);
call create_room('B001', 'R002', 4);
call create_room('B001', 'R003', 4);


call create_room('B003', 'R001', 4);
call create_room('B003', 'R002', 4);
call create_room('B003', 'R003', 4);

call checkout_student('0011');

update building set occupancy = 0;

select * from Building;
select * from Room;

SET FOREIGN_KEY_CHECKS = 0;
truncate table Room;
truncate table Building;
SET FOREIGN_KEY_CHECKS = 1;

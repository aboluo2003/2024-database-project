create trigger update_building_capacity after update on Room
for each row
begin
  -- 计算新的 capacity 变化量
  declare capacity_change int;
  -- 计算新的 occupancy 变化量
  declare occupancy_change int;
  
  if old.capacity != new.capacity or old.occupancy != new.occupancy then
    
    set occupancy_change = new.occupancy - old.occupancy;
    set capacity_change = new.capacity - old.capacity;

    update Building
    set capacity = capacity + capacity_change,
        occupancy = occupancy + occupancy_change
    where BID = new.BID;
  end if;
end;

select * from account;
select * from student;
select * from administrator;

select * from maintenance;

select * from visitor;

select * from room;
select * from building;
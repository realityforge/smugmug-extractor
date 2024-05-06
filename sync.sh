#!/bin/bash
x=1
while [ $x -le 5 ]
do
  git status| grep jpg | tail -n 100 | xargs git add
  git commit -m "Add images"
  git push
done